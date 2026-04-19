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
pooler = "CHEP"  # fixed as per requirement
batch_number = st.text_input("Enter Batch Number")
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# =========================
# PROCESS
# =========================
if uploaded_file and batch_number:

    df = pd.read_excel(uploaded_file)
    business_unit = business_unit.upper()

    # =========================
    # 🇮🇹 ITALY LOGIC (RAW TRANSFORMATION)
    # =========================
    if business_unit == "ITALY":

        def map_pallet_type(value):
            if isinstance(value, str) and "3-B1208A" in value:
                return "CHEP 03 - Euro"
            return value

        df['Prodotto'] = df['Prodotto'].apply(map_pallet_type)

        tracking_df = pd.DataFrame()

        tracking_df['Movement Date'] = df['Dt Bolla']
        tracking_df['Business Unit'] = business_unit
        tracking_df['Pooler'] = pooler
        tracking_df['Movement Direction'] = 'Out'
        tracking_df['Pallet Type'] = df['Prodotto']
        tracking_df['Reference 1'] = df['Ref.CTF']
        tracking_df['Reference 2'] = ''
        tracking_df['Reference 3'] = ''
        tracking_df['Batch Number'] = batch_number

        tracking_df['Sender Location Id'] = business_unit_map[business_unit]['Sender Location Id']
        tracking_df['Sender Name'] = business_unit_map[business_unit]['Sender Name']
        tracking_df['Sender Town'] = ''
        tracking_df['Sender Postcode'] = ''

        tracking_df['Receiver Location Id'] = df['Controparte']
        tracking_df['Receiver Name'] = df['Controparte']
        tracking_df['Receiver Town'] = ''
        tracking_df['Receiver Postcode'] = ''

        tracking_df['Movement Type'] = f"Out - {pooler} Drop Point"
        tracking_df['Quantity'] = df['PLT Caricati']
        tracking_df['Savings'] = ''
        tracking_df['Declared Status'] = 'Declared'

    # =========================
    # 🌍 ALL OTHER COUNTRIES
    # =========================
    else:

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

        df_grouped = df.groupby(
            ['Reference', 'Pallet Type'],
            as_index=False
        ).agg({
            'Qty': 'sum',
            'Date': 'first',
            'Customer': 'first',
            'GID': 'first'
        })

        tracking_df = pd.DataFrame({
            'Movement Date': df_grouped['Date'],
            'Business Unit': business_unit,
            'Pooler': pooler,
            'Movement Direction': 'Out',
            'Pallet Type': df_grouped['Pallet Type'],
            'Reference 1': df_grouped['Reference'],
            'Reference 2': '',
            'Reference 3': '',
            'Batch Number': batch_number,
            'Sender Location Id': business_unit_map[business_unit]['Sender Location Id'],
            'Sender Name': business_unit_map[business_unit]['Sender Name'],
            'Sender Town': '',
            'Sender Postcode': '',
            'Receiver Location Id': df_grouped['GID'],
            'Receiver Name': df_grouped['Customer'],
            'Receiver Town': '',
            'Receiver Postcode': '',
            'Movement Type': f"Out - {pooler} Drop Point",
            'Quantity': df_grouped['Qty'],
            'Savings': '',
            'Declared Status': 'Declared'
        })

    # =========================
    # OUTPUT
    # =========================
    tracking_df = tracking_df.dropna(subset=['Movement Date'])

    output_file = f"{batch_number}.xlsx"

    buffer = BytesIO()
    tracking_df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.success("Tracking file generated!")

    st.download_button(
        label="Download Tracking File",
        data=buffer,
        file_name=output_file,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # cleanup
    del df, tracking_df
