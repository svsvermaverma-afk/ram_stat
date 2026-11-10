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
    
    # Auto-Migration: Purane database me agar mrp ya selling_price column na ho to add kar do
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
            memo_text += f"{it['Item'][:20]:<22}{it['Quantity']:<6}{it['Rate (₹)']:<10.2f}{it['Total (₹)']:<10.
