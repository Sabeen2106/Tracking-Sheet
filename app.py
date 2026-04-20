import streamlit as st
import pandas as pd
from io import BytesIO

# =========================
# BUSINESS UNIT MAPPING
# =========================
business_unit_map = {
    "AUSTRIA": {"Sender Name": "Austria", "Sender Location Id": "5000692765"},
    "DENMARK": {"Sender Name": "Denmark", "Sender Location Id": "5000538928"},
    "DRIFFIELD": {"Sender Name": "Driffield", "Sender Location Id": "5000503209"},
    "FRANCE": {"Sender Name": "France", "Sender Location Id": "0101076563"},
    "IRELAND": {"Sender Name": "Ireland", "Sender Location Id": "5000515873"},
    "ITALY": {"Sender Name": "Italy", "Sender Location Id": "0101230808"},
    "NETHERLANDS": {"Sender Name": "Netherlands", "Sender Location Id": "0100646888"},
    "SPAIN": {"Sender Name": "Spain", "Sender Location Id": "5000449357"},
    "HQ": {"Sender Name": "HQ", "Sender Location Id": "1000358868"}
}

# =========================
# UI
# =========================
st.title("Tracking Sheet Generator")

business_unit = st.selectbox("Select Business Unit", list(business_unit_map.keys()))
pooler = "CHEP"
batch_number = st.text_input("Enter Batch Number")
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# =========================
# PROCESSORS
# =========================

def process_italy(df, business_unit, pooler, batch_number):

    def map_pallet_type(value):
        if isinstance(value, str) and "3-B1208A" in value:
            return "CHEP 03 - Euro"
        return value

    df['Prodotto'] = df['Prodotto'].apply(map_pallet_type)

    return pd.DataFrame({
        'Movement Date': df['Dt Bolla'],
        'Business Unit': business_unit_map[business_unit]['Sender Name'],
        'Pooler': pooler,
        'Movement Direction': 'Out',
        'Pallet Type': df['Prodotto'],
        'Reference 1': df['Ref.CTF'],
        'Reference 2': '',
        'Reference 3': '',
        'Batch Number': batch_number,
        'Sender Location Id': business_unit_map[business_unit]['Sender Location Id'],
        'Sender Name': business_unit_map[business_unit]['Sender Name'],
        'Sender Town': '',
        'Sender Postcode': '',
        'Receiver Location Id': df['Controparte'],
        'Receiver Name': df['Controparte'],
        'Receiver Town': '',
        'Receiver Postcode': '',
        'Movement Type': f"Out - {pooler} Drop Point",
        'Quantity': df['PLT Caricati'],
        'Savings': '',
        'Declared Status': 'Declared'
    })


# =========================
# AUSTRIA (SIMPLIFIED)
# =========================
def process_austria(df, business_unit, pooler, batch_number):

    df = df.iloc[3:].reset_index(drop=True)
    df.columns = df.columns.str.strip()

    df.rename(columns={
        'Unnamed: 4': 'Qty',
        'Unnamed: 6': 'Pallet Type',
        'Unnamed: 8': 'Reference',
        'Unnamed: 9': 'Date',
        'Unnamed: 10': 'Customer',
        'Unnamed: 12': 'GID'
    }, inplace=True)

    df = df[['Qty', 'Pallet Type', 'Reference', 'Date', 'Customer', 'GID']]

    df['Pallet Type'] = df['Pallet Type'].astype(str).str.strip().map({
        '03': 'CHEP 03 - Euro',
        '01': 'CHEP 01 - UK'
    })

    df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d', errors='coerce')
    df['Date'] = df['Date'].dt.strftime('%d/%m/%Y')

    grouped = df.groupby(
        ['Reference', 'Pallet Type'],
        as_index=False
    ).agg({
        'Qty': 'sum',
        'Date': 'first',
        'Customer': 'first',
        'GID': 'first'
    })

    return pd.DataFrame({
        'Movement Date': grouped['Date'],
        'Business Unit': business_unit_map[business_unit]['Sender Name'],
        'Pooler': pooler,
        'Movement Direction': 'Out',
        'Pallet Type': grouped['Pallet Type'],
        'Reference 1': grouped['Reference'],
        'Reference 2': '',
        'Reference 3': '',
        'Batch Number': batch_number,
        'Sender Location Id': business_unit_map[business_unit]['Sender Location Id'],
        'Sender Name': business_unit_map[business_unit]['Sender Name'],
        'Sender Town': '',
        'Sender Postcode': '',
        'Receiver Location Id': grouped['GID'],
        'Receiver Name': grouped['Customer'],
        'Receiver Town': '',
        'Receiver Postcode': '',
        'Movement Type': f"Out - {pooler} Austria Drop Point",
        'Quantity': grouped['Qty'],
        'Savings': '',
        'Declared Status': 'Declared'
    })


# =========================
# PROCESSOR MAP
# =========================
processors = {
    "ITALY": process_italy,
    "AUSTRIA": process_austria
}


# =========================
# DEFAULT
# =========================
def process_default(df, business_unit, pooler, batch_number):
    st.error(f"No processor defined for {business_unit}")
    return pd.DataFrame()


# =========================
# MAIN EXECUTION
# =========================
if uploaded_file and batch_number:

    df = pd.read_excel(uploaded_file)
    business_unit = business_unit.upper()

    processor = processors.get(business_unit, process_default)

    tracking_df = processor(df, business_unit, pooler, batch_number)

    buffer = BytesIO()
    tracking_df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.success("Tracking file generated!")

    st.download_button(
        label="Download Tracking File",
        data=buffer,
        file_name=f"{batch_number}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
