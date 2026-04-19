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
    "HQ": {"Sender Name": "HQ", "Sender Location Id": "1000358868"},
    "CCH": {"Sender Name": "Coca-Cola HBC Northern Ireland Ltd", "Sender Location Id": "5000513592"}
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
# LOAD LOOKUP FILE (CACHED)
# =========================
# =========================
# LOAD LOOKUP FILE (CACHED)
# =========================

@st.cache_data
def load_lookup():
    df_lookup = pd.read_excel("CCH IPP and CHEP.xlsx")

    # Clean columns
    df_lookup.columns = (
        df_lookup.columns
        .str.strip()
        .str.replace('\xa0', '', regex=True)
    )

    # Rename safely
    df_lookup.rename(columns=lambda x: x.strip(), inplace=True)

    df_lookup.rename(columns={
        'Shipment to party Number': 'Customer',
        'Location ID': 'GID'
    }, inplace=True)

    return df_lookup

# CALL FUNCTION OUTSIDE
lookup_df = load_lookup()

# DEBUG
st.write("Lookup Columns:", lookup_df.columns.tolist())

    # SAFER RENAME
    df_lookup.rename(columns=lambda x: x.strip(), inplace=True)

    df_lookup.rename(columns={
        'Shipment to party Number': 'Customer',
        'Location ID': 'GID'
    }, inplace=True)

    # ✅ SAFETY CHECK
    if 'Customer' not in df_lookup.columns:
        raise ValueError(f"Customer column not found in lookup file. Columns: {df_lookup.columns.tolist()}")

    return df_lookup

# =========================
# PROCESSORS (MODULAR)
# =========================

def process_italy(df, lookup_df, business_unit, pooler, batch_number):
    def map_pallet_type(value):
        if isinstance(value, str) and "3-B1208A" in value:
            return "CHEP 03 - Euro"
        return value

    df['Prodotto'] = df['Prodotto'].apply(map_pallet_type)

    return pd.DataFrame({
        'Movement Date': df['Dt Bolla'],
        'Business Unit': business_unit,
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

def process_cch(df, lookup_df, business_unit, pooler, batch_number):
    # Clean columns
    df.columns = df.columns.str.strip().str.replace('\xa0', '', regex=True)

    # Rename
    df.rename(columns={
        'Ship to Party Number': 'Customer',
        'Delivery': 'Reference',
        'Billing doc. date': 'Date'
    }, inplace=True)

    # Clean key
    df['Customer'] = df['Customer'].astype(str).str.strip()

    # Use cached lookup_df (DO NOT reload)
    lookup_df

    lookup_df['Customer'] = lookup_df['Customer'].astype(str).str.strip()

    # Merge (XLOOKUP)
    df = df.merge(
        lookup_df[['Customer', 'GID']],
        on='Customer',
        how='left'
    )

    # Fix date (Excel serial)
    df['Date'] = pd.to_datetime(
        df['Date'],
        unit='D',
        origin='1899-12-30',
        errors='coerce'
    ).dt.strftime('%d/%m/%Y')

    # Pallet
    df['Pallet Type'] = 'CHEP 01 - UK'

    # Build output
    tracking_df = pd.DataFrame()

    tracking_df['Movement Date'] = df['Date']
    tracking_df['Business Unit'] = business_unit_map[business_unit]['Sender Name']
    tracking_df['Pooler'] = pooler
    tracking_df['Movement Direction'] = 'Out'
    tracking_df['Pallet Type'] = df['Pallet Type']
    tracking_df['Reference 1'] = df['Reference']
    tracking_df['Reference 2'] = ''
    tracking_df['Reference 3'] = ''
    tracking_df['Batch Number'] = batch_number

    # Sender
    tracking_df['Sender Location Id'] = business_unit_map[business_unit]['Sender Location Id']
    tracking_df['Sender Name'] = business_unit_map[business_unit]['Sender Name']

    # Receiver
    tracking_df['Receiver Location Id'] = df['GID']
    tracking_df['Receiver Name'] = df['Customer']

    # Movement
    tracking_df['Movement Type'] = f"Out - {pooler} Drop Point"
    tracking_df['Quantity'] = df['Qty']
    tracking_df['Declared Status'] = 'Declared'

    return tracking_df

# =========================
# PROCESSOR MAP
# =========================
processors = {
    "ITALY": process_italy,
    "CCH": process_cch
}
# =========================
# No Processor Defined
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

    tracking_df = processor(df, lookup_df, business_unit, pooler, batch_number)
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
