import streamlit as st
import pandas as pd

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
st.title("Tracking Sheet")

business_unit = st.selectbox("Select Business Unit", list(business_unit_map.keys()))
pooler = st.selectbox("Select Pooler", ["CHEP", "LPR"])
batch_number = st.text_input("Enter Batch Number")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# =========================
# PROCESS
# =========================
if uploaded_file and batch_number:

    df = pd.read_excel(uploaded_file)

    # Remove first 3 rows
    df = df.iloc[3:].reset_index(drop=True)

    # Clean column names
    df.columns = df.columns.str.strip()

    # Rename columns
    df.rename(columns={
        'Unnamed: 4': 'Qty',
        'Unnamed: 6': 'Pallet Type',
        'Unnamed: 8': 'Reference',
        'Unnamed: 9': 'Date',
        'Unnamed: 10': 'Customer',
        'Unnamed: 12': 'GID'
    }, inplace=True)

    df = df[['Qty', 'Pallet Type', 'Reference', 'Date', 'Customer', 'GID']]

    # Map pallet types
    df['Pallet Type'] = df['Pallet Type'].astype(str).str.strip().map({
        '03': 'CHEP 03 - Euro',
        '01': 'CHEP 01 - UK'
    })

    # Convert date
    df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d', errors='coerce')
    df['Date'] = df['Date'].dt.strftime('%d/%m/%Y')

    # Group
    df_grouped = df.groupby(
        ['Reference', 'Pallet Type'],
        as_index=False
    ).agg({
        'Qty': 'sum',
        'Date': 'first',
        'Customer': 'first',
        'GID': 'first'
    })

    # Build output
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

    tracking_df = tracking_df.dropna(subset=['Movement Date'])

    # Convert to Excel in memory
    output_file = f"{batch_number}.xlsx"

    from io import BytesIO
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

    # Clean memory
    del df, df_grouped, tracking_df
