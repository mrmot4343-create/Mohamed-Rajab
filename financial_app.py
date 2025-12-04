import streamlit as st
import pandas as pd
from io import BytesIO

# =========================
# تهيئة الجلسة
# =========================
def init_session():
    if "company_settings" not in st.session_state:
        st.session_state.company_settings = {
            "name": "اسم الشركة",
            "type": "شركة خدمية",
            "period": "للسنة المنتهية في 31/12/2024",
            "logo": None,
        }

    if "chart_of_accounts" not in st.session_state:
        st.session_state.chart_of_accounts = get_default_coa(
            st.session_state.company_settings["type"]
        )

    if "trial_balance" not in st.session_state:
        st.session_state.trial_balance = pd.DataFrame(
            columns=["Account Name", "Account Category", "Debit", "Credit"]
        )

# =========================
# دليل حسابات افتراضي
# =========================
def get_default_coa(company_type: str) -> pd.DataFrame:
    if company_type == "شركة تجارية":
        data = [
            ["1001", "Cash", "Asset"],
            ["1101", "Accounts Receivable", "Asset"],
            ["1201", "Inventory", "Asset"],
            ["2001", "Accounts Payable", "Liability"],
            ["3001", "Owner Capital", "Equity"],
            ["3101", "Owner Drawings", "Drawings"],
            ["4001", "Sales Revenue", "Revenue"],
            ["4101", "Sales Returns", "Revenue"],  # ممكن تعتبرها contra
            ["5001", "Cost of Goods Sold", "COGS"],
            ["6001", "Salaries Expense", "Expense"],
            ["6002", "Rent Expense", "Expense"],
            ["6003", "Utilities Expense", "Expense"],
        ]
    else:  # شركة خدمية
        data = [
            ["1001", "Cash", "Asset"],
            ["1101", "Accounts Receivable", "Asset"],
            ["2001", "Accounts Payable", "Liability"],
            ["3001", "Owner Capital", "Equity"],
            ["3101", "Owner Drawings", "Drawings"],
            ["4001", "Service Revenue", "Revenue"],
            ["6001", "Salaries Expense", "Expense"],
            ["6002", "Rent Expense", "Expense"],
            ["6003", "Utilities Expense", "Expense"],
        ]

    return pd.DataFrame(data, columns=["Account Code", "Account Name", "Category"])

# =========================
# دوال مساعدة للحساب
# =========================
def merge_tb_with_coa(tb: pd.DataFrame, coa: pd.DataFrame) -> pd.DataFrame:
    # لو المستخدم كتب نوع الحساب في ميزان المراجعة نستخدمه، وإلا نأخذ من دليل الحسابات
    tb = tb.copy()
    coa_simple = coa[["Account Name", "Category"]]

    tb = pd.merge(
        tb,
        coa_simple,
        on="Account Name",
        how="left",
        suffixes=("", "_coa"),
    )

    # إذا المستخدم اختار نوع يدوي في ميزان المراجعة، نعطيه أولوية
    tb["Final Category"] = tb["Account Category"]
    tb.loc[tb["Final Category"].isna(), "Final Category"] = tb["Category"]
    tb["Final Category"].fillna("Unassigned", inplace=True)

    # تنظيف أرقام
    tb["Debit"] = pd.to_numeric(tb["Debit"], errors="coerce").fillna(0.0)
    tb["Credit"] = pd.to_numeric(tb["Credit"], errors="coerce").fillna(0.0)

    return tb

def compute_income_statement(tb_merged: pd.DataFrame) -> dict:
    df = tb_merged.copy()

    # حساب الرصيد (اعتماداً على طبيعة الحساب)
    def calc_balance(row):
        cat = row["Final Category"]
        debit = row["Debit"]
        credit = row["Credit"]

        if cat in ["Asset", "Expense", "COGS", "Drawings"]:
            return debit - credit
        else:  # Liability, Equity, Revenue, Other Income, Other Expense, Unassigned
            return credit - debit

    df["Balance"] = df.apply(calc_balance, axis=1)

    revenues = df[df["Final Category"] == "Revenue"]["Balance"].sum()
    cogs = df[df["Final Category"] == "COGS"]["Balance"].sum()
    expenses = df[df["Final Category"] == "Expense"]["Balance"].sum()
    other_income = df[df["Final Category"] == "Other Income"]["Balance"].sum()
    other_expense = df[df["Final Category"] == "Other Expense"]["Balance"].sum()

    gross_profit = revenues - cogs
    operating_profit = gross_profit - expenses
    net_other = other_income - other_expense
    net_income = operating_profit + net_other

    return {
        "revenues": revenues,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "expenses": expenses,
        "operating_profit": operating_profit,
        "other_income": other_income,
        "other_expense": other_expense,
        "net_income": net_income,
    }

def compute_balance_sheet(tb_merged: pd.DataFrame, net_income: float) -> dict:
    df = tb_merged.copy()

    def calc_balance(row):
        cat = row["Final Category"]
        debit = row["Debit"]
        credit = row["Credit"]

        if cat in ["Asset", "Expense", "COGS", "Drawings"]:
            return debit - credit
        else:
            return credit - debit

    df["Balance"] = df.apply(calc_balance, axis=1)

    assets = df[df["Final Category"] == "Asset"]["Balance"].sum()
    liabilities = df[df["Final Category"] == "Liability"]["Balance"].sum()
    equity_accounts = df[df["Final Category"] == "Equity"]["Balance"].sum()
    drawings = df[df["Final Category"] == "Drawings"]["Balance"].sum()

    # نفترض أن المسحوبات تقلل حقوق الملكية
    ending_equity = equity_accounts + net_income - drawings

    total_liab_equity = liabilities + ending_equity

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity_raw": equity_accounts,
        "drawings": drawings,
        "net_income": net_income,
        "ending_equity": ending_equity,
        "total_liab_equity": total_liab_equity,
    }

def export_to_excel(tb, coa, is_data, bs_data):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        tb.to_excel(writer, sheet_name="Trial Balance", index=False)
        coa.to_excel(writer, sheet_name="Chart of Accounts", index=False)

        # تحويل قوائم الدخل والميزانية لبيانات قابلة للتصدير
        is_df = pd.DataFrame(
            {
                "Item": [
                    "Revenues",
                    "COGS",
                    "Gross Profit",
                    "Expenses",
                    "Operating Profit",
                    "Other Income",
                    "Other Expense",
                    "Net Income",
                ],
                "Amount": [
                    is_data["revenues"],
                    is_data["cogs"],
                    is_data["gross_profit"],
                    is_data["expenses"],
                    is_data["operating_profit"],
                    is_data["other_income"],
                    is_data["other_expense"],
                    is_data["net_income"],
                ],
            }
        )
        is_df.to_excel(writer, sheet_name="Income Statement", index=False)

        bs_df = pd.DataFrame(
            {
                "Item": [
                    "Assets",
                    "Liabilities",
                    "Equity (Raw)",
                    "Drawings",
                    "Net Income",
                    "Ending Equity",
                    "Liabilities + Equity",
                ],
                "Amount": [
                    bs_data["assets"],
                    bs_data["liabilities"],
                    bs_data["equity_raw"],
                    bs_data["drawings"],
                    bs_data["net_income"],
                    bs_data["ending_equity"],
                    bs_data["total_liab_equity"],
                ],
            }
        )
        bs_df.to_excel(writer, sheet_name="Balance Sheet", index=False)

    output.seek(0)
    return output

# =========================
# واجهة البرنامج
# =========================
def main():
    st.set_page_config(page_title="نظام القوائم المالية", layout="wide")
    init_session()

    settings = st.session_state.company_settings

    # شريط جانبي للتنقل
    page = st.sidebar.radio(
        "اختر الصفحة",
        ["إعدادات الشركة", "دليل الحسابات", "ميزان المراجعة", "القوائم المالية", "تحليل مالي"],
    )

    # عرض اسم الشركة واللوغو أعلى الصفحة
    cols_header = st.columns([4, 1])
    with cols_header[0]:
        st.markdown(f"### {settings['name']}")
        st.markdown(f"**{settings['period']}**")
        st.markdown(f"**نوع الشركة:** {settings['type']}")
    with cols_header[1]:
        if settings["logo"] is not None:
            st.image(settings["logo"], use_column_width=True)

    # ========== صفحة الإعدادات ==========
    if page == "إعدادات الشركة":
        st.subheader("إعدادات الشركة")

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("اسم الشركة", value=settings["name"])
            period = st.text_input("فترة التقرير", value=settings["period"])
            company_type = st.selectbox(
                "نوع الشركة",
                options=["شركة خدمية", "شركة تجارية"],
                index=0 if settings["type"] == "شركة خدمية" else 1,
            )

        with col2:
            logo_file = st.file_uploader("تحميل اللوغو (اختياري)", type=["png", "jpg", "jpeg"])
            if logo_file is not None:
                settings["logo"] = logo_file

        if st.button("حفظ الإعدادات"):
            changed_type = company_type != settings["type"]
            settings["name"] = name
            settings["period"] = period
            settings["type"] = company_type

            # إذا تغير نوع الشركة، نعيد تحميل دليل حسابات افتراضي (مع تحذير بسيط)
            if changed_type:
                st.session_state.chart_of_accounts = get_default_coa(company_type)
                st.warning("تم تغيير نوع الشركة، وتم تحديث دليل الحسابات الافتراضي. يمكنك تعديله من صفحة دليل الحسابات.")
            st.success("تم حفظ الإعدادات بنجاح ✅")

    # ========== صفحة دليل الحسابات ==========
    elif page == "دليل الحسابات":
        st.subheader("دليل الحسابات (Chart of Accounts)")
        st.markdown("يمكنك تعديل، إضافة، أو حذف الحسابات حسب احتياجك.")

        coa = st.session_state.chart_of_accounts

        edited_coa = st.data_editor(
            coa,
            num_rows="dynamic",
            use_container_width=True,
        )

        if st.button("حفظ دليل الحسابات"):
            st.session_state.chart_of_accounts = edited_coa
            st.success("تم حفظ دليل الحسابات ✅")

    # ========== صفحة ميزان المراجعة ==========
    elif page == "ميزان المراجعة":
        st.subheader("ميزان المراجعة (Trial Balance)")
        st.markdown("أضف أو عدّل الحسابات. يمكنك كتابة اسم الحساب، اختيار نوعه (اختياري)، وإدخال المدين والدائن.")

        tb = st.session_state.trial_balance

        # نساعد المستخدم باقتراح أسماء الحسابات من دليل الحسابات
        coa_names = st.session_state.chart_of_accounts["Account Name"].unique().tolist()
        st.markdown("**ملاحظة:** يفضّل أن تتطابق أسماء الحسابات مع الأسماء في دليل الحسابات لتحصل على تقارير أدق.")

        edited_tb = st.data_editor(
            tb,
            num_rows="dynamic",
            use_container_width=True,
        )

        if st.button("حفظ ميزان المراجعة"):
            st.session_state.trial_balance = edited_tb
            st.success("تم حفظ ميزان المراجعة ✅")

        # عرض مجموع المدين والدائن للتأكد من الاتزان
        if not edited_tb.empty:
            total_debit = pd.to_numeric(edited_tb["Debit"], errors="coerce").fillna(0).sum()
            total_credit = pd.to_numeric(edited_tb["Credit"], errors="coerce").fillna(0).sum()
            st.write(f"**إجمالي المدين:** {total_debit:,.2f}")
            st.write(f"**إجمالي الدائن:** {total_credit:,.2f}")
            if abs(total_debit - total_credit) < 0.01:
                st.success("ميزان المراجعة متزن ✅")
            else:
                st.error("ميزان المراجعة غير متزن ⚠️")

    # ========== صفحة القوائم المالية ==========
    elif page == "القوائم المالية":
        st.subheader("القوائم المالية")

        tb = st.session_state.trial_balance
        coa = st.session_state.chart_of_accounts

        if tb.empty:
            st.warning("ميزان المراجعة فارغ. الرجاء إدخال البيانات أولاً.")
            return

        tb_merged = merge_tb_with_coa(tb, coa)
        is_data = compute_income_statement(tb_merged)
        bs_data = compute_balance_sheet(tb_merged, is_data["net_income"])

        col_is, col_bs = st.columns(2)

        # --------- قائمة الدخل ---------
        with col_is:
            st.markdown("### قائمة الدخل (Income Statement)")
            st.write(f"الإيرادات: {is_data['revenues']:,.2f}")
            st.write(f"تكلفة المبيعات: {is_data['cogs']:,.2f}")
            st.write(f"**مجمل الربح:** {is_data['gross_profit']:,.2f}")
            st.write(f"المصاريف التشغيلية: {is_data['expenses']:,.2f}")
            st.write(f"**الربح التشغيلي:** {is_data['operating_profit']:,.2f}")
            st.write(f"إيرادات أخرى: {is_data['other_income']:,.2f}")
            st.write(f"مصروفات أخرى: {is_data['other_expense']:,.2f}")
            st.write(f"**صافي الربح:** {is_data['net_income']:,.2f}")

        # --------- الميزانية / المركز المالي ---------
        with col_bs:
            st.markdown("### الميزانية العمومية / قائمة المركز المالي (Balance Sheet)")
            st.write(f"**إجمالي الأصول:** {bs_data['assets']:,.2f}")
            st.write(f"إجمالي الخصوم: {bs_data['liabilities']:,.2f}")
            st.write(f"حقوق الملكية (قبل التعديل): {bs_data['equity_raw']:,.2f}")
            st.write(f"المسحوبات: {bs_data['drawings']:,.2f}")
            st.write(f"صافي الربح: {bs_data['net_income']:,.2f}")
            st.write(f"**حقوق الملكية في نهاية الفترة:** {bs_data['ending_equity']:,.2f}")
            st.write(f"**إجمالي الخصوم + حقوق الملكية:** {bs_data['total_liab_equity']:,.2f}")

            if abs(bs_data["assets"] - bs_data["total_liab_equity"]) < 0.01:
                st.success("المعادلة متحققة: الأصول = الخصوم + حقوق الملكية ✅")
            else:
                st.error("الأصول لا تساوي الخصوم + حقوق الملكية ⚠️ تحقق من ميزان المراجعة أو التصنيف.")

        # زر تصدير
        excel_file = export_to_excel(tb, coa, is_data, bs_data)
        st.download_button(
            label="📥 تحميل ملف Excel للقوائم وميزان المراجعة",
            data=excel_file,
            file_name="financial_reports.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ========== صفحة التحليل المالي ==========
    elif page == "تحليل مالي":
        st.subheader("تحليل مالي بسيط")

        tb = st.session_state.trial_balance
        coa = st.session_state.chart_of_accounts

        if tb.empty:
            st.warning("ميزان المراجعة فارغ. الرجاء إدخال البيانات أولاً.")
            return

        tb_merged = merge_tb_with_coa(tb, coa)
        is_data = compute_income_statement(tb_merged)
        bs_data = compute_balance_sheet(tb_merged, is_data["net_income"])

        revenues = is_data["revenues"]
        net_income = is_data["net_income"]
        assets = bs_data["assets"]
        liabilities = bs_data["liabilities"]

        st.markdown("### نسب وأرقام مهمة")

        if revenues != 0:
            gross_margin = is_data["gross_profit"] / revenues
            net_margin = net_income / revenues
            st.write(f"هامش مجمل الربح: {gross_margin * 100:,.2f}%")
            st.write(f"هامش صافي الربح: {net_margin * 100:,.2f}%")
        else:
            st.write("لا يمكن حساب هوامش الربح لعدم وجود إيرادات.")

        if liabilities != 0:
            debt_to_asset = liabilities / assets if assets != 0 else 0
            st.write(f"نسبة الديون إلى الأصول: {debt_to_asset * 100:,.2f}%")

        st.info("يمكنك تطوير هذه الصفحة لاحقاً لإضافة نسب أكثر (التداول، السيولة السريعة، العائد على الأصول، إلخ).")

if __name__ == "__main__":
    main()
