import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import plotly.express as px

# ---------- Streamlit Page Config ----------
st.set_page_config(page_title="Food Wastage Dashboard", page_icon="🍽️", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>🍽️ Local Food Wastage Management</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# ---------- Database Config ----------
DB_PATH = "food_wastage.db"

@st.cache_resource(ttl=3600)
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Food_ID TEXT NOT NULL,
            Provider_ID TEXT NOT NULL,
            Food_Item TEXT NOT NULL,
            Quantity REAL NOT NULL,
            Expiry_Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Meal_Type TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            Contact TEXT NOT NULL,
            City TEXT NOT NULL
        )
    """)
    conn.commit()

create_tables()

# ---------- Load Data ----------
@st.cache_data(ttl=60)
def load_food_listings():
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM food_listings", conn)
        return df
    except Exception as e:
        st.error("❌ Failed to load food listings.")
        st.code(str(e))
        st.stop()

@st.cache_data(ttl=60)
def load_providers_by_city(city):
    try:
        conn = get_connection()
        query = "SELECT Name, Contact, City FROM providers WHERE City = ?"
        df = pd.read_sql(query, conn, params=(city,))
        return df
    except Exception as e:
        st.error("❌ Error fetching contacts.")
        st.code(str(e))
        return pd.DataFrame()

# ---------- Tabs ----------
tab1, tab2 = st.tabs(["📦 Food Listings & Add", "📊 Dashboard"])

# ---------- Tab 1 ----------
with tab1:
    st.subheader("📦 Available Food Listings")
    df = load_food_listings()

    if df.empty:
        st.info("ℹ️ No food listings found.")
    else:
        st.dataframe(df, use_container_width=True)

    st.subheader("🏙️ Filter by City")
    if not df.empty and "Location" in df.columns:
        cities = sorted(df["Location"].dropna().unique())
        city = st.selectbox("Select a City:", cities)

        filtered_df = df[df["Location"] == city]
        st.dataframe(filtered_df, use_container_width=True)

        st.subheader("📇 Contact Providers")
        if st.button("Show Contacts in Selected City"):
            contact_df = load_providers_by_city(city)
            if contact_df.empty:
                st.warning("⚠️ No providers found in this city.")
            else:
                st.dataframe(contact_df, use_container_width=True)
    else:
        st.info("ℹ️ No data available to filter by city.")

    st.subheader("➕ Add New Food Listing")
    with st.form("add_food_form"):
        col1, col2 = st.columns(2)
        with col1:
            food_id = st.text_input("Food ID")
            provider_id = st.text_input("Provider ID")
            food_item = st.text_input("Food Item")
            quantity = st.number_input("Quantity (kg)", min_value=0.1, format="%.2f")
            expiry = st.date_input("Expiry Date", min_value=date.today())
        with col2:
            location = st.text_input("Location")
            meal_type = st.selectbox("Meal Type", ["Veg", "Non-Veg", "Vegan"])
            provider_name = st.text_input("Provider Name")
            provider_contact = st.text_input("Provider Contact")

        submitted = st.form_submit_button("Add Food")
        if submitted:
            # Validate inputs (no empty strings, quantity > 0)
            if all([
                food_id.strip(), provider_id.strip(), food_item.strip(),
                location.strip(), provider_name.strip(), provider_contact.strip(),
                meal_type  # meal_type is from selectbox, always valid
            ]) and quantity > 0:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute("""
                        INSERT INTO food_listings (
                            Food_ID, Provider_ID, Food_Item, Quantity, Expiry_Date, Location, Meal_Type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        food_id.strip(), provider_id.strip(), food_item.strip(),
                        quantity, expiry.strftime("%Y-%m-%d"),
                        location.strip(), meal_type
                    ))

                    cursor.execute("""
                        INSERT OR IGNORE INTO providers (Name, Contact, City)
                        VALUES (?, ?, ?)
                    """, (provider_name.strip(), provider_contact.strip(), location.strip()))

                    conn.commit()
                    st.success("✅ New food listing added successfully!")
                except Exception as e:
                    st.error(f"❌ Failed to add food listing: {e}")
            else:
                st.warning("⚠️ Please fill all required fields correctly.")

# ---------- Tab 2 ----------
with tab2:
    st.subheader("📊 Dashboard Overview")
    df = load_food_listings()

    if df.empty:
        st.info("ℹ️ No data available for dashboard.")
    else:
        # Convert Expiry_Date to datetime (handle errors)
        df["Expiry_Date"] = pd.to_datetime(df["Expiry_Date"], errors='coerce')
        today = pd.Timestamp.today().normalize()

        # Clean empty Food_Item and Meal_Type (fallback to 'Unknown')
        df['Food_Item'] = df['Food_Item'].fillna('Unknown').replace('', 'Unknown')
        df['Meal_Type'] = df['Meal_Type'].fillna('Unknown').replace('', 'Unknown')

        # Total metrics
        total_listings = len(df)
        total_quantity = df["Quantity"].sum()
        unique_food_items = df['Food_Item'].nunique()
        unique_providers = df['Provider_ID'].nunique()
        expired_items = df[df['Expiry_Date'] < today]
        num_expired = len(expired_items)

        # Show KPIs in 4 columns
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 Total Listings", total_listings)
        col2.metric("⚖️ Total Quantity (kg)", f"{total_quantity:.2f}")
        col3.metric("🍽️ Unique Food Items", unique_food_items)
        col4.metric("🛎️ Unique Providers", unique_providers)

        st.markdown(f"⚠️ **Expired Listings:** {num_expired}")

        # Quantity by Location
        st.subheader("🌍 Quantity by Location")
        quantity_by_location = df.groupby("Location")["Quantity"].sum().reset_index()
        fig_location = px.bar(
            quantity_by_location,
            x="Location",
            y="Quantity",
            color="Quantity",
            color_continuous_scale="viridis",
            labels={"Quantity": "Total Quantity (kg)"},
            title="Food Quantity by Location"
        )
        st.plotly_chart(fig_location, use_container_width=True)

        # Quantity by Meal Type
        st.subheader("🍱 Quantity by Meal Type")
        quantity_by_meal = df.groupby("Meal_Type")["Quantity"].sum().reset_index()
        fig_meal = px.pie(
            quantity_by_meal,
            names="Meal_Type",
            values="Quantity",
            title="Meal Type Distribution",
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        st.plotly_chart(fig_meal, use_container_width=True)

        # Top 5 Food Items by Quantity
        st.subheader("🍔 Top 5 Food Items by Quantity Wasted")
        top_food = df.groupby("Food_Item")["Quantity"].sum().sort_values(ascending=False).head(5).reset_index()
        fig_top_food = px.bar(
            top_food,
            x="Food_Item",
            y="Quantity",
            labels={"Quantity": "Total Quantity (kg)"},
            title="Top 5 Food Items by Quantity"
        )
        st.plotly_chart(fig_top_food, use_container_width=True)

        # Expiry Status Pie Chart
        df['Is_Expired'] = df['Expiry_Date'] < today
        expiry_status = df['Is_Expired'].value_counts().rename({True: 'Expired', False: 'Not Expired'}).reset_index()
        expiry_status.columns = ['Expiry Status', 'Count']
        fig_expiry_pie = px.pie(
            expiry_status,
            names='Expiry Status',
            values='Count',
            title='Expired vs Non-Expired Food Listings',
            color='Expiry Status',
            color_discrete_map={'Expired':'red', 'Not Expired':'green'}
        )
        st.plotly_chart(fig_expiry_pie, use_container_width=True)

        # Average Quantity per Meal Type
        avg_quantity_meal = df.groupby("Meal_Type")["Quantity"].mean().reset_index()
        st.subheader("⚖️ Average Quantity per Meal Type")
        fig_avg_meal = px.bar(
            avg_quantity_meal,
            x="Meal_Type",
            y="Quantity",
            labels={"Quantity": "Avg Quantity (kg)"},
            title="Average Quantity per Meal Type"
        )
        st.plotly_chart(fig_avg_meal, use_container_width=True)

        # Expiry Trend Over Time
        st.subheader("⏳ Expiry Trend Over Time")
        try:
            expiry_trend = df.dropna(subset=["Expiry_Date"]).groupby("Expiry_Date")["Quantity"].sum().reset_index()
            fig_time = px.line(
                expiry_trend,
                x="Expiry_Date",
                y="Quantity",
                markers=True,
                title="Quantity Expiring Over Time",
                labels={"Quantity": "Quantity (kg)", "Expiry_Date": "Date"}
            )
            st.plotly_chart(fig_time, use_container_width=True)
        except Exception as e:
            st.error("⚠️ Could not generate expiry chart.")
            st.code(str(e))