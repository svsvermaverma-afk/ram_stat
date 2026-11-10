import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

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
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            bill_no INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            items_summary TEXT,
            subtotal REAL,
            discount REAL,
            tax REAL,
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
st.sidebar.caption("Retail Billing & Stock Management")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Navigation", ["🧾 New Bill / POS", "📦 Inventory Management", "📊 Sales & Reports"])

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
            unit_price = float(row["price"])
            stock_qty = int(row["stock"])

            st.caption(f"**Selling Price:** ₹{unit_price:.2f} | **Available Stock:** {stock_qty} pcs")
            qty = st.number_input("Quantity", min_value=1, max_value=stock_qty, value=1, step=1)

            if st.button("➕ Add to Cart", use_container_width=True):
                match_index = next((i for i, item in enumerate(st.session_state.cart) if item["Item"] == selected_item), None)
                if match_index is not None:
                    new_q = st.session_state.cart[match_index]["Quantity"] + qty
                    if new_q <= stock_qty:
                        st.session_state.cart[match_index]["Quantity"] = new_q
                        st.session_state.cart[match_index]["Total (₹)"] = new_q * unit_price
                        st.success(f"Updated quantity for {selected_item}")
                    else:
                        st.error(f"Cannot exceed available stock ({stock_qty})")
                else:
                    st.session_state.cart.append({
                        "Item": selected_item,
                        "Rate (₹)": unit_price,
                        "Quantity": qty,
                        "Total (₹)": unit_price * qty
                    })
                    st.success(f"Added {selected_item} to bill")
        else:
            st.warning("Inventory empty hai! Kripya pehle inventory section me jakar items add karein.")

    with col_cart:
        st.subheader("Invoice Preview")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df, use_container_width=True)

            subtotal = float(cart_df["Total (₹)"].sum())
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            with col_d2:
                gst_pct = st.number_input("GST / Tax (%)", min_value=0.0, max_value=28.0, value=0.0, step=1.0)

            discount_val = (subtotal * discount_pct) / 100
            after_discount = subtotal - discount_val
            tax_val = (after_discount * gst_pct) / 100
            final_total = round(after_discount + tax_val, 2)

            st.write(f"**Subtotal:** ₹{subtotal:.2f} | **Discount:** -₹{discount_val:.2f} | **GST:** +₹{tax_val:.2f}")
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
                        INSERT INTO sales (customer_name, items_summary, subtotal, discount, tax, total_amount, bill_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (cust_name, items_summary, subtotal, discount_val, tax_val, final_total, bill_time))
                    
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
                        "tax": tax_val,
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
        memo_text = f"""
==================================================
              SOURYA STATIONERY
      Narayan Talkies Road, Sihora, Jabalpur (M.P.)
            Phone: +91-XXXXXXXXXX
==================================================
Bill No: #{b['bill_no']}              Date: {b['date']}
Customer: {b['customer']}
--------------------------------------------------
{'Item':<22}{'Qty':<6}{'Rate':<10}{'Total':<10}
--------------------------------------------------\n"""
        for it in b['items']:
            memo_text += f"{it['Item'][:20]:<22}{it['Quantity']:<6}{it['Rate (₹)']:<10.2f}{it['Total (₹)']:<10.2f}\n"

        memo_text += f"""--------------------------------------------------
Subtotal:                             ₹{b['subtotal']:.2f}
Discount:                            -₹{b['discount']:.2f}
Tax / GST:                           +₹{b['tax']:.2f}
--------------------------------------------------
GRAND TOTAL:                          ₹{b['total']:.2f}
==================================================
   * Goods once sold will not be taken back *
         Dhanyawad! Phir Padhaariyega!
==================================================
"""
        st.code(memo_text, language="text")
        st.download_button(
            label="📥 Download Receipt (.txt)",
            data=memo_text,
            file_name=f"Sourya_Stationery_Bill_{b['bill_no']}.txt",
            mime="text/plain"
        )

# ----------------- 2. INVENTORY SECTION -----------------
elif menu == "📦 Inventory Management":
    st.title("📦 Sourya Stationery - Inventory")

    tab_add, tab_view = st.tabs(["➕ Add / Update Item", "📋 Stock List"])

    with tab_add:
        with st.form("inventory_form", clear_on_submit=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                name = st.text_input("Item Name (e.g., Classmate Notebook, Doms Pencil Box)").strip().title()
                category = st.selectbox("Category", [
                    "Notebooks & Registers", 
                    "Pens, Pencils & Erasers", 
                    "Drawing & Art Supplies", 
                    "Files, Folders & Envelopes", 
                    "Desk Accessories & Calculators", 
                    "General Goods"
                ])
            with col_i2:
                price = st.number_input("Selling Price (₹)", min_value=1.0, step=1.0)
                stock = st.number_input("Quantity to Add", min_value=1, step=1)

            submit = st.form_submit_button("Save to Inventory", use_container_width=True)
            if submit:
                if name:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO inventory (name, category, price, stock)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            price = excluded.price,
                            stock = stock + excluded.stock,
                            category = excluded.category
                    """, (name, category, price, stock))
                    conn.commit()
                    conn.close()
                    st.success(f"'{name}' successfully inventory me save ho gaya!")
                else:
                    st.error("Item name likhna zaroori hai.")

    with tab_view:
        conn = get_connection()
        df_stock = pd.read_sql("SELECT id as 'ID', name as 'Item Name', category as 'Category', price as 'Rate (₹)', stock as 'Available Qty' FROM inventory", conn)
        conn.close()

        if not df_stock.empty:
            st.dataframe(df_stock, use_container_width=True)
            low_stock = df_stock[df_stock["Available Qty"] <= 5]
            if not low_stock.empty:
                st.error("⚠️ Low Stock Alert (Quantity ≤ 5)")
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
