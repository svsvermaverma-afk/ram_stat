import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
import re
import json
from fpdf import FPDF

# 1. Page Configuration (Mobile & Desktop Responsive)
st.set_page_config(
    page_title="Sourya Stationery - POS", 
    page_icon="📚", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
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

# 2. Database Connection & Schema Setup
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
    
    # Auto-migration for inventory
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

    # Sales Table with items_json for permanent bill printing
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            bill_no INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            items_summary TEXT,
            subtotal REAL,
            discount REAL,
            total_amount REAL,
            bill_date TEXT,
            items_json TEXT
        )
    """)
    
    # Check if items_json exists in sales
    c.execute("PRAGMA table_info(sales)")
    sales_cols = [column[1] for column in c.fetchall()]
    if "items_json" not in sales_cols:
        c.execute("ALTER TABLE sales ADD COLUMN items_json TEXT")

    conn.commit()
    conn.close()

init_db()

# Helper: Google Sheet URL converter
def get_gsheet_csv_url(sheet_url):
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    if match:
        doc_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
    return sheet_url

# Helper: Database se Bill Fetch karna (Reload hone par bhi bill na khoye)
def get_bill_from_db(bill_id=None):
    conn = get_connection()
    c = conn.cursor()
    if bill_id:
        c.execute("SELECT bill_no, customer_name, bill_date, subtotal, discount, total_amount, items_json FROM sales WHERE bill_no = ?", (bill_id,))
    else:
        # Aakhri generate hua bill
        c.execute("SELECT bill_no, customer_name, bill_date, subtotal, discount, total_amount, items_json FROM sales ORDER BY bill_no DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    
    if row:
        items = []
        if row[6]:
            try:
                items = json.loads(row[6])
            except Exception:
                items = []
        return {
            "bill_no": row[0],
            "customer": row[1],
            "date": row[2],
            "subtotal": float(row[3] or 0.0),
            "discount": float(row[4] or 0.0),
            "total": float(row[5] or 0.0),
            "items": items
        }
    return None

# 3. PDF Generator: A4 Landscape 2 Bills Side-by-Side
def build_side_by_side_pdf(bill_data):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # Center Separator
    pdf.set_draw_color(180, 180, 180)
    pdf.line(148.5, 5, 148.5, 205)

    def draw_single_bill(x_offset, copy_type):
        w = 136
        h = 195
        y_top = 8

        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.rect(x_offset, y_top, w, h)

        # Header 1
        pdf.set_xy(x_offset + 3, y_top + 2)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(50, 4, "Prop: Shriram Chandravanshi", 0, 0, "L")
        pdf.cell(32, 4, f"[{copy_type}]", 0, 0, "C")
        pdf.cell(48, 4, "Mob: 9039626922, 8770713490", 0, 1, "R")

        # Shop Name
        pdf.set_x(x_offset)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(w, 6, "SOURYA STATIONERY & SPORTS", 0, 1, "C")

        # Sub-title
        pdf.set_x(x_offset)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(w, 4, "School, College, Office Stationery, Sports Goods, Gifts & General Items", 0, 1, "C")

        # Address Band
        pdf.set_x(x_offset)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w, 4.5, "Talkies Road, Ward No. 5, Sihora, Jabalpur (M.P.)", 1, 1, "C")

        # Meta Info
        pdf.ln(1)
        curr_y = pdf.get_y()
        pdf.set_xy(x_offset + 3, curr_y)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(16, 5, "Bill No / Kr:", 0, 0)
        pdf.set_text_color(180, 0, 0)
        pdf.cell(35, 5, f"#{bill_data['bill_no']}", 0, 0)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(40, 5, "", 0, 0)
        pdf.cell(15, 5, "Date:", 0, 0)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(27, 5, f"{bill_data['date']}", 0, 1, "R")

        # Customer
        pdf.set_x(x_offset + 3)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(20, 5, "Shreeman:", 0, 0)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(110, 5, f"{bill_data['customer']}", "B", 1)

        # Table Header
        pdf.ln(2)
        table_y = pdf.get_y()
        pdf.set_xy(x_offset + 2, table_y)
        col_sno, col_desc, col_qty, col_rate, col_amt = 10, 64, 18, 20, 20

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_sno, 6, "S.N.", 1, 0, "C")
        pdf.cell(col_desc, 6, "Description / Vivaran", 1, 0, "C")
        pdf.cell(col_qty, 6, "Qty", 1, 0, "C")
        pdf.cell(col_rate, 6, "Rate (Rs)", 1, 0, "C")
        pdf.cell(col_amt, 6, "Amount", 1, 1, "C")

        # Items Rows
        row_start_y = pdf.get_y()
        max_rows = 11
        row_height = 7
        total_table_height = max_rows * row_height

        pdf.set_font("Helvetica", "", 8)
        for idx in range(max_rows):
            r_y = row_start_y + (idx * row_height)
            pdf.set_xy(x_offset + 2, r_y)
            if idx < len(bill_data['items']):
                it = bill_data['items'][idx]
                name = str(it.get('Item', 'Item'))[:30]
                qty = str(it.get('Quantity', 1))
                rate = f"{float(it.get('Rate (INR)', 0)):.1f}"
                tot = f"{float(it.get('Total (INR)', 0)):.1f}"

                pdf.cell(col_sno, row_height, str(idx + 1), "LR", 0, "C")
                pdf.cell(col_desc, row_height, f" {name}", "LR", 0, "L")
                pdf.cell(col_qty, row_height, qty, "LR", 0, "C")
                pdf.cell(col_rate, row_height, f"{rate} ", "LR", 0, "R")
                pdf.cell(col_amt, row_height, f"{tot} ", "LR", 1, "R")
            else:
                pdf.cell(col_sno, row_height, "", "LR", 0, "C")
                pdf.cell(col_desc, row_height, "", "LR", 0, "L")
                pdf.cell(col_qty, row_height, "", "LR", 0, "C")
                pdf.cell(col_rate, row_height, "", "LR", 0, "R")
                pdf.cell(col_amt, row_height, "", "LR", 1, "R")

        bottom_y = row_start_y + total_table_height
        pdf.line(x_offset + 2, bottom_y, x_offset + 2 + w - 4, bottom_y)

        # Discount
        if bill_data.get('discount', 0) > 0:
            pdf.set_xy(x_offset + 2, bottom_y)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.cell(col_sno + col_desc + col_qty, 5, "Discount Applied", 1, 0, "R")
            pdf.cell(col_rate + col_amt, 5, f"- Rs. {bill_data['discount']:.2f} ", 1, 1, "R")
            bottom_y += 5

        # Grand Total
        pdf.set_xy(x_offset + 2, bottom_y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_sno + col_desc + col_qty, 7, "KUL YOG / GRAND TOTAL:", 1, 0, "R")
        pdf.cell(col_rate + col_amt, 7, f"Rs. {bill_data['total']:.2f} ", 1, 1, "R")

        # Signatures
        pdf.set_xy(x_offset + 4, y_top + h - 14)
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(60, 4, "* Goods once sold will not be taken back", 0, 0, "L")
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(68, 4, "Vaste - Sourya Stationery & Sports", 0, 1, "R")
        pdf.set_xy(x_offset + 4, y_top + h - 9)
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(60, 4, "Thank you! Please visit again.", 0, 0, "L")
        pdf.cell(68, 4, "(Authorized Signatory)", 0, 1, "R")

    draw_single_bill(6, "CUSTOMER COPY")
    draw_single_bill(154, "SHOP COPY")

    return bytes(pdf.output())

# 4. Session State Setup
if "cart" not in st.session_state:
    st.session_state.cart = []

# Sidebar Navigation
st.sidebar.markdown("## 📚 Sourya Stationery")
st.sidebar.caption("Narayan Talkies Road, Sihora")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Navigation", ["🧾 New Bill / POS", "📦 Inventory Management", "📊 Sales & Reports"])

# ----------------- MODULE 1: BILLING (POS) -----------------
if menu == "🧾 New Bill / POS":
    st.title("📚 Sourya Stationery - POS Counter")
    
    conn = get_connection()
    df_items = pd.read_sql("SELECT * FROM inventory WHERE stock > 0", conn)
    conn.close()

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
                        st.error(f"Stock se jyada quantity add nahi kar sakte! (Available: {stock_qty})")
                else:
                    st.session_state.cart.append({
                        "Item": selected_item,
                        "Rate (INR)": sell_price,
                        "Quantity": qty,
                        "Total (INR)": sell_price * qty
                    })
                    st.success(f"Added {selected_item}")
        else:
            st.warning("Inventory me stock uplabdh nahi hai. Kripya pehle inventory sync karein.")

    with col_cart:
        st.subheader("Cart & Checkout")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df, use_container_width=True)

            subtotal = float(cart_df["Total (INR)"].sum())
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
                    items_json_str = json.dumps(st.session_state.cart)

                    for item in st.session_state.cart:
                        c.execute("UPDATE inventory SET stock = stock - ? WHERE name = ?", (item["Quantity"], item["Item"]))

                    c.execute("""
                        INSERT INTO sales (customer_name, items_summary, subtotal, discount, total_amount, bill_date, items_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (cust_name, items_summary, subtotal, discount_val, final_total, bill_time, items_json_str))
                    
                    conn.commit()
                    conn.close()

                    st.session_state.cart = []
                    st.success("Bill permanently save ho gaya!")
                    st.rerun()

            with btn_col2:
                if st.button("🗑️ Clear Cart", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
        else:
            st.info("Cart khali hai.")

    # ---------------- BILL VIEW & REPRINT SECTION ----------------
    # Reload hone par bhi SQLite database se latest bill hamesha screen par available rahega
    active_bill = get_bill_from_db()
    
    if active_bill and active_bill['items']:
        st.markdown("---")
        b_col1, b_col2 = st.columns([2, 1])
        
        with b_col1:
            st.subheader(f"🧾 Last Generated Bill: #{active_bill['bill_no']} ({active_bill['customer']})")
            st.caption(f"Date: {active_bill['date']} | Total Amount: Rs. {active_bill['total']:.2f}")

        with b_col2:
            # Agar koi aur purana bill reprint karna ho
            conn = get_connection()
            all_bills = pd.read_sql("SELECT bill_no, customer_name FROM sales ORDER BY bill_no DESC LIMIT 20", conn)
            conn.close()
            
            if not all_bills.empty:
                bill_options = {f"Bill #{r['bill_no']} - {r['customer_name']}": r['bill_no'] for _, r in all_bills.iterrows()}
                selected_label = st.selectbox("Purana Bill Reprint Karein:", list(bill_options.keys()))
                chosen_id = bill_options[selected_label]
                if chosen_id != active_bill['bill_no']:
                    active_bill = get_bill_from_db(chosen_id)

        # PDF download button
        if active_bill and active_bill.get('items'):
            pdf_bytes = build_side_by_side_pdf(active_bill)
            st.download_button(
                label=f"📄 Download Dual Bill #{active_bill['bill_no']} (PDF)",
                data=pdf_bytes,
                file_name=f"Sourya_Stationery_Dual_Bill_{active_bill['bill_no']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# ----------------- MODULE 2: INVENTORY -----------------
elif menu == "📦 Inventory Management":
    st.title("📦 Sourya Stationery - Inventory")

    tab_gsheet, tab_manual, tab_excel, tab_view = st.tabs([
        "🌐 Google Sheet Sync", "➕ Manual Entry", "📂 Excel Bulk Upload", "📋 Stock List"
    ])

    with tab_gsheet:
        st.subheader("🌐 Sync Inventory from Google Sheets")
        default_sheet_url = "https://docs.google.com/spreadsheets/d/1rHEQ8o7u3mvGxh5VJuyJ9EU4-h9TH2Abx4niXByBHV4/edit?usp=sharing"
        sheet_url_input = st.text_input("Google Sheet Share Link", value=default_sheet_url)
        
        load_btn = st.button("🔄 Fetch / Reload from Google Sheets", type="primary", use_container_width=True)
            
        if load_btn or ("gsheet_cache_df" in st.session_state):
            try:
                csv_url = get_gsheet_csv_url(sheet_url_input)
                df_gsheet = pd.read_csv(csv_url)
                df_gsheet.columns = [str(c).strip().lower() for c in df_gsheet.columns]
                st.session_state.gsheet_cache_df = df_gsheet
                
                st.success("Google Sheet se live data fetch ho gaya!")
                st.dataframe(df_gsheet, use_container_width=True)
                
                required_cols = {"name", "category", "mrp", "selling_price", "stock"}
                if required_cols.issubset(set(df_gsheet.columns)):
                    if st.button("💾 Save / Update into Local Database", type="secondary", use_container_width=True):
                        conn = get_connection()
                        c = conn.cursor()
                        count = 0
                        for _, r in df_gsheet.iterrows():
                            if pd.notna(r["name"]):
                                c.execute("""
                                    INSERT INTO inventory (name, category, price, mrp, selling_price, stock)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    ON CONFLICT(name) DO UPDATE SET
                                        category = excluded.category,
                                        price = excluded.price,
                                        mrp = excluded.mrp,
                                        selling_price = excluded.selling_price,
                                        stock = excluded.stock
                                """, (
                                    str(r["name"]).strip().title(),
                                    str(r.get("category", "General Goods")).strip(),
                                    float(r.get("selling_price", 0.0)),
                                    float(r.get("mrp", 0.0)),
                                    float(r.get("selling_price", 0.0)),
                                    int(r.get("stock", 0))
                                ))
                                count += 1
                        conn.commit()
                        conn.close()
                        st.success(f"{count} items database me sync aur update ho gaye!")
                else:
                    st.error(f"Columns missing hain! Sheet me ye columns hone chahiye: {list(required_cols)}")
            except Exception as e:
                st.error(f"Google Sheet fetch karne me error: {e}")

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
                    "Desk Accessories & Calculators",
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
                            """, (
                                str(r["name"]).strip().title(), 
                                str(r["category"]).strip(), 
                                float(r["selling_price"]), 
                                float(r["mrp"]), 
                                float(r["selling_price"]), 
                                int(r["stock"])
                            ))
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
            low_stock = df_stock[df_stock["Available Qty"] <= 5]
            if not low_stock.empty:
                st.error("⚠️ Low Stock Alert (Quantity ≤ 5):")
                st.dataframe(low_stock)
        else:
            st.info("Inventory khali hai.")

# ----------------- MODULE 3: SALES HISTORY -----------------
elif menu == "📊 Sales & Reports":
    st.title("📊 Sales Report & History")
    conn = get_connection()
    df_sales = pd.read_sql("SELECT bill_no as 'Bill ID', customer_name as 'Customer', items_summary as 'Items', total_amount as 'Total (Rs.)', bill_date as 'Date' FROM sales ORDER BY bill_no DESC", conn)
    conn.close()

    if not df_sales.empty:
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Total Revenue", f"Rs. {df_sales['Total (Rs.)'].sum():.2f}")
        col_m2.metric("Total Bills Generated", len(df_sales))
        st.dataframe(df_sales, use_container_width=True)
        
        # Download Complete Sales Report
        csv = df_sales.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Sales Report (CSV)",
            data=csv,
            file_name="Sourya_Stationery_Sales_Report.csv",
            mime="text/csv"
        )
    else:
        st.info("Abhi tak koi bill generate nahi hua hai.")
