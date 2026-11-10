# Printable Cash Memo View (Branded with Narayan Talkies Road, Sihora)
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