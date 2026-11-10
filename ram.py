import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# Page Configuration
st.set_page_config(
    page_title="Sourya Stationery - POS & Inventory", 
    page_icon="📚", 
    layout="wide"
)

# Database Connection & Setup
def get_connection():
    return sqlite3.connect("sourya_stationery.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Inventory Table creation
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT,
            mrp REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0
        )
    """)
    
    # Auto-Migration for columns
    c.execute("PRAGMA table_info(inventory)")
    cols = [column[1] for column in c.fetchall()]
    
    if "selling_price" not in cols:
        if "price" in cols:
            c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL DEFAULT 0")
            c.execute("UPDATE inventory SET selling_price = price")
        else:
            c.execute("ALTER TABLE inventory ADD COLUMN selling_price REAL DEFAULT 0")
            
    if "mrp" not in cols:
        c.execute("ALTER TABLE inventory ADD COLUMN mrp REAL DEFAULT 0")
        c.execute("UPDATE inventory SET mrp = selling_price")

    # Sales Table
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

# Session State Variables
if "cart" not in st.session_state:
    st.session_state.cart = []
if "last_bill" not in st.session_state:
    st.session_state.last_bill = None

# Sidebar Branding & Navigation
st.sidebar.markdown("## 📚 Sourya Stationery")
st.sidebar.caption("Narayan Talkies Road, Sihora (M.P.)")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Navigation", ["🧾 New Bill / POS", "📦 Inventory (Add / Excel Upload)", "📊 Sales & Reports"])

# ----------------- 1. BILLING SECTION -----------------
if menu == "🧾 New Bill / POS":
    st.title("📚 Sourya Stationery - Billing Counter")
    
    conn = get_connection()
    df_items = pd.read_sql("SELECT * FROM inventory WHERE stock > 0", conn)
    conn.close()

    col_entry, col_cart = st.columns([1, 1.2])

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

            st.info(f"**MRP:** ₹{mrp_price:.2f} | **Selling Price:** ₹{sell_price:.2f} | **Stock:** {stock_qty} pcs")
            qty = st.number_input("Quantity", min_value=1, max_value=max(1, stock_qty), value=1, step=1)

            if st.button("➕ Add to Cart", use_container_width=True):
                match_index = next((i for i, item in enumerate(st.session_state.cart) if item["Item"] == selected_item), None)
                if match_index is not None:
                    new_q = st.session_state.cart[match_index]["Quantity"] + qty
                    if new_q <= stock_qty:
                        st.session_state.cart[match_index]["Quantity"] = new_q
                        st.session_state.cart[match_index]["Total (₹)"] = new_q * sell_price
                        st.success(f"Updated quantity for {selected_item}")
                    else:
                        st.error(f"Stock se jyada quantity nahi jod sakte! Available: {stock_qty}")
                else:
                    st.session_state.cart.append({
                        "Item": selected_item,
                        "Rate (₹)": sell_price,
                        "Quantity": qty,
                        "Total (₹)": sell_price * qty
                    })
                    st.success(f"Added {selected_item} to bill")
        else:
            st.warning("Inventory empty hai! Pehle Inventory me jakar items add karein.")

    with col_cart:
        st.subheader("Invoice Preview")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df, use_container_width=True)

            subtotal = float(cart_df["Total (₹)"].sum())
            
            discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            discount_val = (subtotal * discount_pct) / 100
            final_total = round(subtotal - discount_val, 2)

            st.write(f"**Subtotal:** ₹{subtotal:.2f} | **Discount ({discount_pct}%):** -₹{discount_val:.2f}")
            st.markdown(f"### **Grand Total: ₹{final_total:.2f}**")

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

    # Printable Cash Memo View
    if st.session_state.last_bill:
        b = st.session_state.last_bill
        st.markdown("---")
        st.subheader("🖨️ Printable Cash Memo")
        
        memo_lines = [
            "=" * 50,
            "              SOURYA STATIONERY",
            "      Narayan Talkies Road, Sihora, Jabalpur (M.P.)",
            "            Phone: +91-XXXXXXXXXX",
            "=" * 50,
            f"Bill No: #{b['bill_no']:<15} Date: {b['date']}",
            f"Customer: {b['customer']}",
            "-" * 50,
            f"{'Item':<22}{'Qty':<6}{'Rate':<10}{'Total':<10}",
            "-" * 50
        ]
        
        for it in b['items']:
            item_name = str(it['Item'])[:20]
            item_qty = int(it['Quantity'])
            item_rate = float(it['Rate (₹)'])
            item_tot = float(it['Total (₹)'])
            line = f"{item_name:<22}{item_qty:<6}{item_rate:<10.2f}{item_tot:<10.2f}"
            memo_lines.append(line)
            
        memo_lines.extend([
            "-" * 50,
            f"Subtotal:                             ₹{b['subtotal']:.2f}",
            f"Discount:                            -₹{b['discount']:.2f}",
            "-" * 50,
            f"GRAND TOTAL:                          ₹{b['total']:.2f}",
            "=" * 50,
            "   * Goods once sold will not be taken back *",
            "         Dhanyawad! Phir Padhaariyega!",
            "=" * 50
        ])
        
        memo_text = "\n".join(memo_lines)
        st.code(memo_text, language="text")
        st.download_button(
            label="📥 Download Receipt (.txt)",
            data=memo_text,
            file_name=f"Sourya_Stationery_Bill_{b['bill_no']}.txt",
            mime="text/plain"
        )

# ----------------- 2. INVENTORY SECTION -----------------
elif menu == "📦 Inventory (Add / Excel Upload)":
    st.title("📦 Sourya Stationery - Inventory & Stock")

    tab_manual, tab_excel, tab_view = st.tabs(["➕ Manual Single Item", "📂 Excel / CSV File Upload", "📋 Current Stock List"])

    with tab_manual:
        with st.form("manual_form", clear_on_submit=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                name = st.text_input("Item Name (e.g., Classmate Notebook 120p)").strip().title()
                category = st.selectbox("Category", [
                    "Notebooks & Registers", 
                    "Pens, Pencils & Erasers", 
                    "Drawing & Art Supplies", 
                    "Files, Folders & Envelopes", 
                    "Desk Accessories & Calculators", 
                    "General Goods"
                ])
            with col_i2:
                mrp = st.number_input("MRP (₹)", min_value=1.0, value=50.0, step=1.0)
                selling_price = st.number_input("Selling Price (₹)", min_value=1.0, value=45.0, step=1.0)
                stock = st.number_input("Stock Quantity", min_value=1, step=1)

            submit = st.form_submit_button("Save Permanently to Inventory", use_container_width=True)
            if submit:
                if name:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO inventory (name, category, mrp, selling_price, stock)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            category = excluded.category,
                            mrp = excluded.mrp,
                            selling_price = excluded.selling_price,
                            stock = stock + excluded.stock
                    """, (name, category, mrp, selling_price, stock))
                    conn.commit()
                    conn.close()
                    st.success(f"'{name}' successfully save ho gaya!")
                else:
                    st.error("Item name likhna zaroori hai.")

    with tab_excel:
        st.subheader("Bulk Stock Upload via Excel / CSV")
        st.write("Excel columns: `name`, `category`, `mrp`, `selling_price`, `stock`")
        
        sample_df = pd.DataFrame([
            {"name": "Classmate Notebook", "category": "Notebooks & Registers", "mrp": 60.0, "selling_price": 55.0, "stock": 50},
            {"name": "Reynolds Ball Pen Blue", "category": "Pens, Pencils & Erasers", "mrp": 10.0, "selling_price": 10.0, "stock": 100},
            {"name": "Doms Color Kit", "category": "Drawing & Art Supplies", "mrp": 150.0, "selling_price": 140.0, "stock": 20}
        ])
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            sample_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Download Sample Excel Template",
            data=output.getvalue(),
            file_name="sample_stationery_format.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        uploaded_file = st.file_uploader("Upload Excel ya CSV File", type=["xlsx", "xls", "csv"])
        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_upload = pd.read_csv(uploaded_file)
                else:
                    df_upload = pd.read_excel(uploaded_file)

                df_upload.columns = [c.strip().lower() for c in df_upload.columns]
                required_cols = {"name", "category", "mrp", "selling_price", "stock"}

                if required_cols.issubset(set(df_upload.columns)):
                    st.write("File Preview:")
                    st.dataframe(df_upload.head(10), use_container_width=True)

                    if st.button("🚀 Upload & Permanently Save to Database", type="primary"):
                        conn = get_connection()
                        c = conn.cursor()
                        count = 0
                        for _, r in df_upload.iterrows():
                            item_name = str(r["name"]).strip().title()
                            cat = str(r["category"]).strip()
                            mrp_val = float(r["mrp"])
                            sp_val = float(r["selling_price"])
                            stk_val = int(r["stock"])

                            c.execute("""
                                INSERT INTO inventory (name, category, mrp, selling_price, stock)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT(name) DO UPDATE SET
                                    category = excluded.category,
                                    mrp = excluded.mrp,
                                    selling_price = excluded.selling_price,
                                    stock = stock + excluded.stock
                            """, (item_name, cat, mrp_val, sp_val, stk_val))
                            count += 1

                        conn.commit()
                        conn.close()
                        st.success(f"Zabardast! {count} items database me permanently save ho gaye.")
                else:
                    st.error(f"Excel me ye saare columns hone zaroori hain: {', '.join(required_cols)}")
            except Exception as e:
                st.error(f"File padhne me error: {e}")

    with tab_view:
        conn = get_connection()
        df_stock = pd.read_sql("SELECT id as 'ID', name as 'Item Name', category as 'Category', mrp as 'MRP (₹)', selling_price as 'Selling Price (₹)', stock as 'Available Qty' FROM inventory", conn)
        conn.close()

        if not df_stock.empty:
            st.dataframe(df_stock, use_container_width=True)
            low_stock = df_stock[df_stock["Available Qty"] <= 5]
            if not low_stock.empty:
                st.error("⚠️ Low Stock Alert (Quantity ≤ 5):")
                st.dataframe(low_stock)
        else:
            st.info("Inventory khali hai.")

# ----------------- 3. SALES HISTORY -----------------
elif menu == "📊 Sales & Reports":
    st.title("📊 Sourya Stationery - Sales Report")

    conn = get_connection()
    df_sales = pd.read_sql("SELECT bill_no as 'Bill ID', customer_name as 'Customer', items_summary as 'Items', total_amount as 'Total (₹)', bill_date as 'Date' FROM sales ORDER BY bill_no DESC", conn)
    conn.close()

    if not df_sales.empty:
        metric1, metric2 = st.columns(2)
        metric1.metric("Total Revenue", f"₹{df_sales['Total (₹)'].sum():.2f}")
        metric2.metric("Total Bills Cut", len(df_sales))

        st.dataframe(df_sales, use_container_width=True)
    else:
        st.info("Abhi tak koi bill generate nahi hua hai.")
