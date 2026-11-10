import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
from fpdf import FPDF

# 1. Responsive Viewport for Mobile & Desktop
st.set_page_config(
    page_title="Sourya Stationery - POS", 
    page_icon="📚", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Mobile Touch Targets & Receipt Layout
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    button[kind="primary"], button[kind="secondary"] {
        min-height: 44px;
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Database Connection & Setup
def get_connection():
    return sqlite3.connect("sourya_stationery.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT,
            price REAL DEFAULT 0,
            mrp REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0
        )
    """)
    
    # Auto-Migration checks
    c.execute("PRAGMA table_info(inventory)")
    cols = [column[1] for column in c.fetchall()]
    
    if "selling_price" not in cols:
        c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL DEFAULT 0")
        if "price" in cols:
            c.execute("UPDATE inventory SET selling_price = price")
            
    if "mrp" not in cols:
        c.execute("ALTER TABLE inventory ADD COLUMN mrp REAL DEFAULT 0")
        c.execute("UPDATE inventory SET mrp = selling_price")

    if "price" not in cols:
        c.execute("ALTER TABLE inventory ADD COLUMN price REAL DEFAULT 0")
        c.execute("UPDATE inventory SET price = selling_price")

    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            bill_no INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            items_summary TEXT,
            subtotal REAL,
            discount REAL,
            total_amount REAL,
            bill_date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Helper: Generate Clean Thermal / Standard PDF Receipt
def build_pdf_receipt(bill_data):
    pdf = FPDF(format=(80, 200)) # 80mm thermal/mobile slip width
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()
    
    # Header
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 6, "SOURYA STATIONERY", ln=True, align="C")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "Narayan Talkies Road, Sihora, Jabalpur (M.P.)", ln=True, align="C")
    pdf.cell(0, 4, "Mob: +91-XXXXXXXXXX", ln=True, align="C")
    pdf.line(4, pdf.get_y() + 1, 76, pdf.get_y() + 1)
    pdf.ln(3)

    # Metadata
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, f"Bill No: #{bill_data['bill_no']}  |  Date: {bill_data['date']}", ln=True)
    pdf.cell(0, 4, f"Customer: {bill_data['customer']}", ln=True)
    pdf.line(4, pdf.get_y() + 1, 76, pdf.get_y() + 1)
    pdf.ln(3)

    # Item Table Headings
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(32, 5, "Item", 0, 0)
    pdf.cell(10, 5, "Qty", 0, 0, "C")
    pdf.cell(15, 5, "Rate", 0, 0, "R")
    pdf.cell(15, 5, "Total", 0, 1, "R")
    pdf.line(4, pdf.get_y(), 76, pdf.get_y())
    pdf.ln(1)

    # Item Rows (Selling Price only)
    pdf.set_font("Helvetica", "", 8)
    for it in bill_data['items']:
        name = str(it['Item'])[:18]
        qty = str(it['Quantity'])
        rate = f"{float(it['Rate (INR)']):.1f}"
        tot = f"{float(it['Total (INR)']):.1f}"
        pdf.cell(32, 4, name, 0, 0)
        pdf.cell(10, 4, qty, 0, 0, "C")
        pdf.cell(15, 4, rate, 0, 0, "R")
        pdf.cell(15, 4, tot, 0, 1, "R")

    pdf.line(4, pdf.get_y() + 1, 76, pdf.get_y() + 1)
    pdf.ln(2)

    # Summary
    pdf.cell(45, 4, "Subtotal:", 0, 0)
    pdf.cell(27, 4, f"Rs. {bill_data['subtotal']:.2f}", 0, 1, "R")
    
    if bill_data['discount'] > 0:
        pdf.cell(45, 4, "Discount:", 0, 0)
        pdf.cell(27, 4, f"- Rs. {bill_data['discount']:.2f}", 0, 1, "R")
        
    pdf.line(4, pdf.get_y() + 1, 76, pdf.get_y() + 1)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(45, 6, "GRAND TOTAL:", 0, 0)
    pdf.cell(27, 6, f"Rs. {bill_data['total']:.2f}", 0, 1, "R")

    # Footer
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(0, 3, "Goods once sold will not be taken back", ln=True, align="C")
    pdf.cell(0, 3, "Dhanyawad! Phir Padhaariyega!", ln=True, align="C")

    return bytes(pdf.output())

# Session State
if "cart" not in st.session_state:
    st.session_state.cart = []
if "last_bill" not in st.session_state:
    st.session_state.last_bill = None

# Sidebar
st.sidebar.markdown("## 📚 Sourya Stationery")
st.sidebar.caption("Narayan Talkies Road, Sihora")
menu = st.sidebar.radio("Navigation", ["🧾 New Bill / POS", "📦 Inventory Management", "📊 Sales & Reports"])

# ----------------- 1. BILLING SECTION -----------------
if menu == "🧾 New Bill / POS":
    st.title("📚 Sourya Stationery - POS Counter")
    
    conn = get_connection()
    df_items = pd.read_sql("SELECT * FROM inventory WHERE stock > 0", conn)
    conn.close()

    # Layout adjusts cleanly on Mobile (stacks vertically) & Desktop (side-by-side)
    col_entry, col_cart = st.columns([1, 1], gap="medium")

    with col_entry:
        st.subheader("Add Item to Bill")
        cust_name = st.text_input("Customer Name / Mobile", value="Cash Customer")
        
        if not df_items.empty:
            item_list = df_items["name"].tolist()
            selected_item = st.selectbox("Search & Select Item", item_list)
            
            row = df_items[df_items["name"] == selected_item].iloc[0]
            mrp_price = float(row.get("mrp", row.get("selling_price", 0.0)))
            sell_price = float(row.get("selling_price", row.get("price", 0.0)))
            stock_qty = int(row.get("stock", 0))

            st.info(f"**MRP:** Rs. {mrp_price:.2f} | **Selling Price:** Rs. {sell_price:.2f} | **In Stock:** {stock_qty} pcs")
            qty = st.number_input("Quantity", min_value=1, max_value=max(1, stock_qty), value=1, step=1)

            if st.button("➕ Add to Cart", use_container_width=True):
                match_index = next((i for i, item in enumerate(st.session_state.cart) if item["Item"] == selected_item), None)
                if match_index is not None:
                    new_q = st.session_state.cart[match_index]["Quantity"] + qty
                    if new_q <= stock_qty:
                        st.session_state.cart[match_index]["Quantity"] = new_q
                        st.session_state.cart[match_index]["Total (INR)"] = new_q * sell_price
                        st.success(f"Updated quantity for {selected_item}")
                    else:
                        st.error(f"Stock se jyada quantity add nahi kar sakte! (Stock: {stock_qty})")
                else:
                    st.session_state.cart.append({
                        "Item": selected_item,
                        "Rate (INR)": sell_price,
                        "Quantity": qty,
                        "Total (INR)": sell_price * qty
                    })
                    st.success(f"Added {selected_item}")
        else:
            st.warning("Inventory me stock uplabdh nahi hai. Kripya naye items add karein.")

    with col_cart:
        st.subheader("Cart & Checkout")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df, use_container_width=True)

            subtotal = float(cart_df["Total (INR)"].sum())
            
            col_disc, col_dummy = st.columns([1, 1])
            with col_disc:
                discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            
            discount_val = (subtotal * discount_pct) / 100
            final_total = round(subtotal - discount_val, 2)

            st.write(f"**Subtotal:** Rs. {subtotal:.2f} | **Discount:** - Rs. {discount_val:.2f}")
            st.markdown(f"### **Grand Total: Rs. {final_total:.2f}**")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("✅ Generate Bill", use_container_width=True, type="primary"):
                    conn = get_connection()
                    c = conn.cursor()
                    
                    items_summary = ", ".join([f"{i['Item']} ({i['Quantity']}x)" for i in st.session_state.cart])
                    bill_time = datetime.now().strftime("%d-%m-%Y %I:%M %p")

                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET stock = stock - ? WHERE name = ?", (item["Quantity"], item["Item"]))

                    c.execute("""
                        INSERT INTO sales (customer_name, items_summary, subtotal, discount, total_amount, bill_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (cust_name, items_summary, subtotal, discount_val, final_total, bill_time))
                    
                    bill_id = c.lastrowid
                    conn.commit()
                    conn.close()

                    st.session_state.last_bill = {
                        "bill_no": bill_id,
                        "customer": cust_name,
                        "date": bill_time,
                        "items": list(st.session_state.cart),
                        "subtotal": subtotal,
                        "discount": discount_val,
                        "total": final_total
                    }
                    st.session_state.cart = []
                    st.rerun()

            with btn_col2:
                if st.button("🗑️ Clear Cart", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
        else:
            st.info("Cart khali hai.")

    # Bill View & PDF Download Section
    if st.session_state.last_bill:
        b = st.session_state.last_bill
        st.markdown("---")
        st.subheader(f"🧾 Bill #{b['bill_no']} - Printable PDF Ready")

        pdf_bytes = build_pdf_receipt(b)
        
        col_down1, col_down2 = st.columns([1, 1])
        with col_down1:
            st.download_button(
                label="📄 Download PDF Invoice",
                data=pdf_bytes,
                file_name=f"Sourya_Stationery_Bill_{b['bill_no']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# ----------------- 2. INVENTORY SECTION -----------------
elif menu == "📦 Inventory Management":
    st.title("📦 Sourya Stationery - Inventory")

    tab_manual, tab_excel, tab_view = st.tabs(["➕ Manual Entry", "📂 Excel Bulk Upload", "📋 Stock List"])

    with tab_manual:
        with st.form("manual_form", clear_on_submit=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                name = st.text_input("Item Name").strip().title()
                category = st.selectbox("Category", [
                    "Notebooks & Registers", 
                    "Pens, Pencils & Erasers", 
                    "Drawing & Art Supplies", 
                    "Files, Folders & Envelopes", 
                    "General Goods"
                ])
            with col_i2:
                mrp = st.number_input("MRP (Rs.)", min_value=1.0, value=50.0, step=1.0)
                selling_price = st.number_input("Selling Price (Rs.)", min_value=1.0, value=45.0, step=1.0)
                stock = st.number_input("Stock Quantity", min_value=1, step=1)

            if st.form_submit_button("Save to Inventory", use_container_width=True):
                if name:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO inventory (name, category, price, mrp, selling_price, stock)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            category = excluded.category,
                            price = excluded.price,
                            mrp = excluded.mrp,
                            selling_price = excluded.selling_price,
                            stock = stock + excluded.stock
                    """, (name, category, selling_price, mrp, selling_price, stock))
                    conn.commit()
                    conn.close()
                    st.success(f"'{name}' successfully save ho gaya!")
                else:
                    st.error("Item name likhna zaroori hai.")

    with tab_excel:
        st.subheader("Bulk Stock Upload (Excel / CSV)")
        st.write("Columns: `name`, `category`, `mrp`, `selling_price`, `stock`")
        
        sample_df = pd.DataFrame([
            {"name": "Classmate Notebook", "category": "Notebooks & Registers", "mrp": 60.0, "selling_price": 55.0, "stock": 50},
            {"name": "Reynolds Ball Pen Blue", "category": "Pens, Pencils & Erasers", "mrp": 10.0, "selling_price": 10.0, "stock": 100}
        ])
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            sample_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Download Template",
            data=buf.getvalue(),
            file_name="sample_stationery_format.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        uploaded_file = st.file_uploader("Choose file", type=["xlsx", "xls", "csv"])
        if uploaded_file:
            try:
                df_upload = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                df_upload.columns = [c.strip().lower() for c in df_upload.columns]
                required = {"name", "category", "mrp", "selling_price", "stock"}

                if required.issubset(set(df_upload.columns)):
                    if st.button("🚀 Upload & Save to Database", type="primary", use_container_width=True):
                        conn = get_connection()
                        c = conn.cursor()
                        count = 0
                        for _, r in df_upload.iterrows():
                            c.execute("""
                                INSERT INTO inventory (name, category, price, mrp, selling_price, stock)
                                VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT(name) DO UPDATE SET
                                    category = excluded.category,
                                    price = excluded.price,
                                    mrp = excluded.mrp,
                                    selling_price = excluded.selling_price,
                                    stock = stock + excluded.stock
                            """, (str(r["name"]).strip().title(), str(r["category"]).strip(), float(r["selling_price"]), float(r["mrp"]), float(r["selling_price"]), int(r["stock"])))
                            count += 1

                        conn.commit()
                        conn.close()
                        st.success(f"{count} items permanently save ho gaye!")
                else:
                    st.error("Excel me required columns missing hain.")
            except Exception as e:
                st.error(f"Error: {e}")

    with tab_view:
        conn = get_connection()
        df_stock = pd.read_sql("SELECT id as 'ID', name as 'Item Name', category as 'Category', mrp as 'MRP (Rs.)', selling_price as 'Selling Price (Rs.)', stock as 'Available Qty' FROM inventory", conn)
        conn.close()

        if not df_stock.empty:
            st.dataframe(df_stock, use_container_width=True)
        else:
            st.info("Inventory khali hai.")

# ----------------- 3. SALES HISTORY -----------------
elif menu == "📊 Sales & Reports":
    st.title("📊 Sales Report")
    conn = get_connection()
    df_sales = pd.read_sql("SELECT bill_no as 'Bill ID', customer_name as 'Customer', items_summary as 'Items', total_amount as 'Total (Rs.)', bill_date as 'Date' FROM sales ORDER BY bill_no DESC", conn)
    conn.close()

    if not df_sales.empty:
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Total Revenue", f"Rs. {df_sales['Total (Rs.)'].sum():.2f}")
        col_m2.metric("Total Bills Cut", len(df_sales))
        st.dataframe(df_sales, use_container_width=True)
    else:
        st.info("Abhi tak koi bill generate nahi hua hai.")
