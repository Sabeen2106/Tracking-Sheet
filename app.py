import streamlit as st
import pandas as pd
from io import BytesIO
import re

# Sender accounts are separated by pooler so IDs cannot be mixed.
chep_accounts = {
    "Austria": "5000692765",
    "Denmark": "5000538928",
    "Driffield": "5000503209",
    "France": "0101076563",
    "Ireland": "5000515873",
    "Italy": "0101230808",
    "Netherlands": "0100646888",
    "Spain": "5000449357",
    "HQ": "1000358868",
    "Coca-Cola HBC Northern Ireland Ltd": "5000513592",
    "Kepak Group Ltd - Merthyr": "0101280939",
    "Kepak Group Ltd - McIntosh": "0101280937",
    "Kepak Group Ltd - Bodmin": "0101280938",
    "Matthew Walker": "101430678",
    "Valeo Confectionery Limited (Rowse Honey)": "5000465750",
}
ipp_accounts = {
    "Graham's Dairies (Bridge of Allan)": "404262",
    "Graham's Dairies (Nairn) Ltd": "405230",
    "Graham's Dairies - Glenfield": "405730",
    "Matthew Walker": "509465",
    "Valeo Confectionery Limited (Rowse Honey)": "509468",
    "Coca-Cola HBC Northern Ireland Ltd": "405296",
}
accounts_by_pooler = {"CHEP": chep_accounts, "IPP": ipp_accounts}


def generate_ipp_dates(references, today=None):
    """Create random candidate dates from the previous 12 calendar days, excluding Sundays.

    One date per reference keeps grouped movements consistent. These are
    *proposed* dates, not verified actual movement dates.
    """
    import secrets
    today = pd.Timestamp.today().normalize() if today is None else pd.Timestamp(today).normalize()
    eligible = [today - pd.Timedelta(days=i) for i in range(1, 13)
                if (today - pd.Timedelta(days=i)).weekday() != 6]
    return {ref: secrets.choice(eligible) for ref in pd.unique(references)}


def clean_columns(df):
    df.columns = df.columns.astype(str).str.strip().str.replace("\xa0", "", regex=False)
    return df


def clean_gid(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


def map_pallet_type(value, pooler):
    value = str(value).strip().upper()

    if pooler == "IPP":
        if value in ("A1210", "IPP A1210 - UK"):
            return "IPP A1210 - UK"
        if value in ("E812", "IPP E812 - EURO"):
            return "IPP E812 - Euro"
        return value


    if (
        "PALLET 1000X1200 MM" in value
        or "1-B1210A" in value
        or value in ["01", "UK", "1"]
    ):
        return "CHEP 01 - UK"

    if (
        "3-B1208A" in value
        or value in ["03", "EUR", "EURO", "CHEP 80", "3", "CHEP EURO"]
    ):
        return "CHEP 03 - Euro"

    if "8-B0806A" in value or value == "08":
        return "CHEP 08 - Half"

    return value


def convert_date_to_ddmmyyyy(value):
    if pd.isna(value):
        return pd.NaT

    try:
        value_str = str(value).strip()

        if value_str.endswith(".0"):
            value_str = value_str[:-2]

        if value_str.isdigit() and len(value_str) == 8:
            year_start = int(value_str[:4])

            if year_start > 1900:
                return pd.Timestamp(
                    year=int(value_str[0:4]),
                    month=int(value_str[4:6]),
                    day=int(value_str[6:8])
                )

            return pd.Timestamp(
                year=int(value_str[4:8]),
                month=int(value_str[2:4]),
                day=int(value_str[0:2])
            )

        if value_str.isdigit() and len(value_str) == 6:
            return pd.to_datetime(value_str, format="%d%m%y", errors="coerce")

        if value_str.isdigit() and len(value_str) == 5:
            return pd.to_datetime(
                int(value_str),
                unit="D",
                origin="1899-12-30",
                errors="coerce"
            )

        if len(value_str) >= 10:
            date_part = value_str[:11].strip()

            if "-" in date_part:
                parts = date_part.split("-")

                if len(parts) == 3 and len(parts[0]) == 4:
                    return pd.Timestamp(
                        year=int(parts[0]),
                        month=int(parts[1]),
                        day=int(parts[2])
                    )

                if len(parts) == 3 and len(parts[2]) == 4:
                    return pd.to_datetime(
                        date_part,
                        errors="coerce",
                        dayfirst=True
                    )

            if "/" in date_part:
                parts = date_part.split("/")

                if len(parts) == 3 and len(parts[0]) == 4:
                    return pd.Timestamp(
                        year=int(parts[0]),
                        month=int(parts[1]),
                        day=int(parts[2])
                    )

                if len(parts) == 3 and len(parts[2]) == 4:
                    return pd.Timestamp(
                        year=int(parts[2]),
                        month=int(parts[1]),
                        day=int(parts[0])
                    )

        return pd.to_datetime(value_str, errors="coerce", dayfirst=True)

    except Exception:
        return pd.NaT


def safe_format_date(value):
    try:
        if pd.isna(value):
            return ""

        value = pd.to_datetime(value, errors="coerce")

        if pd.isna(value):
            return ""

        if value.year < 2000 or value.year > 2100:
            return ""

        return value.strftime("%d/%m/%Y")

    except Exception:
        return ""


def clean_reference_number(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    if len(value) > 13:
        value = value[-13:]

    return value


def split_spain_customer_gid(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    value = value.lstrip("-").strip()

    match = re.match(r"^(\d+)[\s\-]*(.*)$", value)

    if match:
        return pd.Series({
            "Customer": match.group(2).strip().lstrip("-").strip(),
            "GID": clean_gid(match.group(1).strip())
        })

    return pd.Series({
        "Customer": value,
        "GID": ""
    })


def is_missing_gid(series):
    return (
        series.isna()
        | (series.astype(str).str.strip() == "")
        | (series.astype(str).str.lower().str.strip() == "nan")
    )


def excel_buffer(df):
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


def build_tracking_file(final_df, business_unit, pooler, batch_number):
    columns = [
        "Movement Date", "Business Unit", "Pooler", "Movement Direction",
        "Pallet Type", "Reference 1", "Reference 2", "Reference 3",
        "Batch Number", "Sender Location Id", "Sender Name", "Sender Town",
        "Sender Postcode", "Receiver Location Id", "Receiver Name",
        "Receiver Town", "Receiver Postcode", "Movement Type", "Quantity",
        "Savings", "Declared Status"
    ]

    if final_df.empty:
        return pd.DataFrame(columns=columns)

    final_df = final_df.copy()
    final_df["GID"] = final_df["GID"].apply(clean_gid).astype("string")

    grouped = final_df.groupby(
        ["Reference", "Pallet Type"],
        as_index=False
    ).agg({
        "Quantity": "sum",
        "Movement Date": "first",
        "Customer": "first",
        "GID": "first"
    })

    tracking_df = pd.DataFrame({
        "Movement Date": grouped["Movement Date"],
        "Business Unit": business_unit,
        "Pooler": pooler,
        "Movement Direction": "Out",
        "Pallet Type": grouped["Pallet Type"],
        "Reference 1": grouped["Reference"],
        "Reference 2": "",
        "Reference 3": "",
        "Batch Number": batch_number,
        "Sender Location Id": accounts_by_pooler[pooler][business_unit],
        "Sender Name": business_unit,
        "Sender Town": "",
        "Sender Postcode": "",
        "Receiver Location Id": grouped["GID"].apply(clean_gid),
        "Receiver Name": grouped["Customer"],
        "Receiver Town": "",
        "Receiver Postcode": "",
        "Movement Type": f"Out - {pooler} Drop Point",
        "Quantity": grouped["Quantity"],
        "Savings": "",
        "Declared Status": "Declared"
    })

    return tracking_df[columns]


st.title("PP Tracking Sheet")

pooler = st.selectbox("Select Pooler", ["CHEP", "IPP"])
business_unit = st.selectbox("Select Business Unit / Sender Account", list(accounts_by_pooler[pooler].keys()))
batch_number = st.text_input("Enter Batch Number")

main_file = st.file_uploader("Upload Main Excel File", type=["xlsx"])

if main_file:
    df = pd.read_excel(main_file)
    df = clean_columns(df)

    st.subheader("Map Main File Columns")

    columns = df.columns.tolist()

    if pooler == "CHEP":
        movement_date_col = st.selectbox("Select column for Movement Date", columns)
    else:
        movement_date_col = None
        st.info("IPP: Candidate dates can be generated from the previous 12 calendar days, excluding today and Sundays. Verify dates against actual movements before declaration.")
        generate_dates = st.checkbox("Generate proposed IPP movement dates (requires verification)", value=False)
    quantity_col = st.selectbox("Select column for Quantity", columns)
    pallet_type_col = st.selectbox("Select column for Pallet Type", columns)
    reference_col = st.selectbox("Select column for Reference", columns)
    customer_col = st.selectbox("Select column for Customer", columns)

    if business_unit == "Spain":
        st.info("Spain selected: GID will be extracted from the Customer column automatically.")
        gid_available = "Spain"
        gid_col = None
        lookup_file = None
    else:
        gid_available = st.radio(
            "Is GID / Location ID already available in the main file?",
            ["Yes", "No"]
        )

        if gid_available == "Yes":
            gid_col = st.selectbox("Select column for GID / Location ID", columns)
            lookup_file = None
        else:
            gid_col = None

            if business_unit == "HQ":
                lookup_file = st.file_uploader(
                    "Upload HQ Location Mapping Table",
                    type=["xlsx"]
                )
            else:
                lookup_file = st.file_uploader(
                    "Upload Customer to GID Matching File",
                    type=["xlsx"]
                )

    if st.button("Prepare Data"):
        if not batch_number:
            st.error("Please enter Batch Number.")
            st.stop()

        if pooler == "IPP" and not generate_dates:
            st.error("Please confirm whether to generate proposed IPP dates, or use CHEP to retain source dates.")
            st.stop()

        st.session_state["prepared_pooler"] = pooler
        st.session_state["prepared_business_unit"] = business_unit
        work_df = df.copy()

        if pooler == "CHEP":
            work_df["Movement Date Parsed"] = work_df[movement_date_col].apply(convert_date_to_ddmmyyyy)
            work_df["Movement Date Parsed"] = pd.to_datetime(work_df["Movement Date Parsed"], errors="coerce")
        else:
            # Retain any source date for audit/reference; never overwrite the uploaded file.
            source_date_col = next((c for c in work_df.columns if c.lower() in
                                    ("movement date", "date", "transaction date")), None)
            work_df["Original Movement Date"] = work_df[source_date_col] if source_date_col else ""
            reference_dates = generate_ipp_dates(work_df[reference_col].apply(clean_reference_number))
            work_df["Movement Date Parsed"] = work_df[reference_col].apply(clean_reference_number).map(reference_dates)
            st.session_state["ipp_dates_generated"] = True

        work_df["Movement Date"] = work_df["Movement Date Parsed"].apply(safe_format_date)

        work_df["Quantity"] = pd.to_numeric(
            work_df[quantity_col],
            errors="coerce"
        ).fillna(0)

        work_df = work_df[work_df["Quantity"] != 0].copy()

        work_df["Pallet Type"] = work_df[pallet_type_col].apply(lambda value: map_pallet_type(value, pooler))
        work_df["Reference"] = work_df[reference_col].apply(clean_reference_number)

        if business_unit == "Spain":
            spain_split = work_df[customer_col].apply(split_spain_customer_gid)

            work_df["Customer"] = spain_split["Customer"]
            work_df["GID"] = spain_split["GID"].apply(clean_gid).astype("string")

            st.session_state["work_df"] = work_df
            st.session_state["need_lookup_mapping"] = False

        else:
            work_df["Customer"] = work_df[customer_col].astype(str).str.strip()

            if gid_available == "Yes":
                work_df["GID"] = work_df[gid_col].apply(clean_gid).astype("string")
                st.session_state["work_df"] = work_df
                st.session_state["need_lookup_mapping"] = False

            else:
                if lookup_file is None:
                    st.error("Please upload the required GID matching file.")
                    st.stop()

                lookup_df = pd.read_excel(lookup_file)
                lookup_df = clean_columns(lookup_df)

                st.session_state["lookup_df"] = lookup_df
                st.session_state["work_df_without_gid"] = work_df
                st.session_state["need_lookup_mapping"] = True
                st.session_state["business_unit_for_lookup"] = business_unit


if st.session_state.get("need_lookup_mapping", False):
    lookup_df = st.session_state["lookup_df"]
    work_df = st.session_state["work_df_without_gid"]
    lookup_business_unit = st.session_state["business_unit_for_lookup"]

    if lookup_business_unit == "HQ":
        st.subheader("HQ Location Mapping")

        main_address_col = st.selectbox(
            "Select Address Line 1 column from Main File",
            work_df.columns.tolist(),
            key="hq_main_address_col"
        )

        lookup_address_col = st.selectbox(
            "Select Address1 column from HQ Mapping Table",
            lookup_df.columns.tolist(),
            key="hq_lookup_address_col"
        )

        lookup_gid_col = st.selectbox(
            "Select CHEP GID column from HQ Mapping Table",
            lookup_df.columns.tolist(),
            key="hq_lookup_gid_col"
        )

        if st.button("Apply HQ Mapping"):
            work_df["Address Match Key"] = (
                work_df[main_address_col]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            lookup_df["Address Match Key"] = (
                lookup_df[lookup_address_col]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            lookup_df = lookup_df[["Address Match Key", lookup_gid_col]].copy()

            lookup_df.rename(columns={lookup_gid_col: "GID"}, inplace=True)

            lookup_df = lookup_df.dropna(subset=["Address Match Key"])
            lookup_df = lookup_df.drop_duplicates(
                subset=["Address Match Key"],
                keep="first"
            )

            lookup_df["GID"] = lookup_df["GID"].apply(clean_gid).astype("string")

            work_df = work_df.merge(
                lookup_df,
                on="Address Match Key",
                how="left"
            )

            work_df["GID"] = work_df["GID"].apply(clean_gid).astype("string")

            st.session_state["work_df"] = work_df
            st.session_state["need_lookup_mapping"] = False

    else:
        st.subheader("Customer to GID Mapping")

        lookup_customer_col = st.selectbox(
            "Select Customer column in lookup file",
            lookup_df.columns.tolist(),
            key="lookup_customer_col"
        )

        lookup_gid_col = st.selectbox(
            "Select GID / Location ID column",
            lookup_df.columns.tolist(),
            key="lookup_gid_col"
        )

        if st.button("Apply Customer Lookup"):
            lookup_df = lookup_df[[lookup_customer_col, lookup_gid_col]].copy()

            lookup_df.rename(columns={
                lookup_customer_col: "Customer",
                lookup_gid_col: "GID"
            }, inplace=True)

            lookup_df["Customer"] = lookup_df["Customer"].astype(str).str.strip()
            lookup_df["GID"] = lookup_df["GID"].apply(clean_gid).astype("string")

            lookup_df = lookup_df.dropna(subset=["Customer"])
            lookup_df = lookup_df.drop_duplicates(
                subset=["Customer"],
                keep="first"
            )

            work_df = work_df.merge(
                lookup_df,
                on="Customer",
                how="left"
            )

            work_df["GID"] = work_df["GID"].apply(clean_gid).astype("string")

            st.session_state["work_df"] = work_df
            st.session_state["need_lookup_mapping"] = False


if "work_df" in st.session_state and (st.session_state.get("prepared_pooler") != pooler or st.session_state.get("prepared_business_unit") != business_unit):
    st.warning("Pooler changed. Please click Prepare Data again before generating files.")

if "work_df" in st.session_state and st.session_state.get("prepared_pooler") == pooler and st.session_state.get("prepared_business_unit") == business_unit:
    work_df = st.session_state["work_df"].copy()
    work_df["GID"] = work_df["GID"].apply(clean_gid).astype("string")

    if pooler == "IPP":
        st.warning("IPP dates are randomly generated proposals, not evidence of actual movement dates. Check and correct them against supporting records before using a declaration file.")
        st.dataframe(work_df[["Reference", "Movement Date", "Original Movement Date"]].drop_duplicates(), hide_index=True)

    today = pd.Timestamp.today().normalize()

    work_df["Days Old"] = (
        today - work_df["Movement Date Parsed"]
    ).dt.days

    processing_window = {"CHEP": 89, "IPP": 12}[pooler]
    old_date_df = work_df[work_df["Days Old"] > processing_window].copy()

    if not old_date_df.empty:
        st.warning(f"Some movement dates exceed the {pooler} processing window.")
        st.subheader(f"Review Dates Over {processing_window} Days")

        unique_old_dates = old_date_df[["Reference", "Movement Date"]].drop_duplicates()

        for _, old_row in unique_old_dates.iterrows():
            reference = old_row["Reference"]
            old_date = old_row["Movement Date"]

            st.error(
                f"Reference {reference}: {old_date} exceeds {processing_window} days. "
                f"{pooler} late declaration charges may apply."
            )

            amend_date = st.checkbox(
                f"Amend date for reference {reference}",
                key=f"amend_date_{reference}"
            )

            if amend_date:
                new_date = st.date_input(
                    f"Enter revised date for reference {reference}",
                    key=f"new_date_{reference}"
                )

                work_df.loc[
                    work_df["Reference"] == reference,
                    "Movement Date Parsed"
                ] = pd.to_datetime(new_date)

                work_df.loc[
                    work_df["Reference"] == reference,
                    "Movement Date"
                ] = safe_format_date(new_date)

    missing_gid_df = work_df[is_missing_gid(work_df["GID"])].copy()

    gid_inputs = {}
    remove_keys = []

    if not missing_gid_df.empty:
        st.warning("Some rows are missing GID / Location ID.")
        st.subheader("Missing GID Input by Customer and Reference")

        unique_missing = missing_gid_df[
            ["Reference", "Customer"]
        ].drop_duplicates()

        for _, row in unique_missing.iterrows():
            reference = row["Reference"]
            customer = row["Customer"]

            related_rows = missing_gid_df[
                (missing_gid_df["Reference"] == reference)
                & (missing_gid_df["Customer"] == customer)
            ]

            total_quantity = related_rows["Quantity"].sum()
            movement_date = related_rows["Movement Date"].iloc[0]

            gid_key = f"{reference}|||{customer}"

            with st.container():
                st.markdown("---")
                st.write(f"Customer: {customer}")
                st.write(f"Reference Number: {reference}")
                st.write(f"Movement Date: {movement_date}")
                st.write(f"Total Quantity: {total_quantity}")

                gid_inputs[gid_key] = st.text_input(
                    "Please enter GID for this reference",
                    key=f"gid_input_{gid_key}"
                )

                remove = st.checkbox(
                    "GID not found - remove this reference",
                    key=f"remove_row_{gid_key}"
                )

                if remove:
                    remove_keys.append(gid_key)

    else:
        st.success("No missing GIDs found.")

    verified_ipp_dates = True
    if pooler == "IPP":
        verified_ipp_dates = st.checkbox(
            "I have checked the proposed IPP dates against actual movement records and corrected any discrepancies."
        )

    if st.button("Generate Final Files"):
        if pooler == "IPP" and not verified_ipp_dates:
            st.error("Please verify the IPP movement dates against actual records before exporting.")
            st.stop()
        work_df["GID"] = work_df["GID"].apply(clean_gid).astype("string")

        for gid_key, gid_value in gid_inputs.items():
            gid_value = clean_gid(gid_value)

            if gid_value:
                reference, customer = gid_key.split("|||", 1)

                work_df.loc[
                    (work_df["Reference"] == reference)
                    & (work_df["Customer"] == customer),
                    "GID"
                ] = gid_value

        work_df["GID"] = work_df["GID"].apply(clean_gid).astype("string")

        remove_indexes = []

        for gid_key in remove_keys:
            reference, customer = gid_key.split("|||", 1)

            matched_indexes = work_df[
                (work_df["Reference"] == reference)
                & (work_df["Customer"] == customer)
            ].index.tolist()

            remove_indexes.extend(matched_indexes)

        removed_rows_df = work_df.loc[remove_indexes].copy()

        gid_required_df = work_df[
            is_missing_gid(work_df["GID"])
            & ~work_df.index.isin(remove_indexes)
        ].copy()

        final_df = work_df[
            ~is_missing_gid(work_df["GID"])
            & ~work_df.index.isin(remove_indexes)
        ].copy()

        tracking_df = build_tracking_file(final_df, business_unit, pooler, batch_number)
        removed_tracking_df = build_tracking_file(removed_rows_df, business_unit, pooler, batch_number)
        gid_required_tracking_df = build_tracking_file(gid_required_df, business_unit, pooler, batch_number)

        st.success("Files generated successfully.")

        st.download_button(
            label="Download Tracking Sheet",
            data=excel_buffer(tracking_df),
            file_name=f"{batch_number}_tracking_sheet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


        st.download_button(
            label="Download Removed Rows",
            data=excel_buffer(removed_tracking_df),
            file_name="Removed rows.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
