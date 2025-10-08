import streamlit as st
import pandas as pd
import numpy as np
import json
import io
# Cần cài đặt: pip install google-genai docx2txt numpy pandas streamlit
try:
    from google import genai
    from google.genai.errors import APIError
except ImportError:
    st.error("Lỗi: Vui lòng cài đặt thư viện 'google-genai' (pip install google-genai)")

try:
    import docx2txt
except ImportError:
    st.error("Lỗi: Vui lòng cài đặt thư viện 'docx2txt' để đọc file Word (pip install docx2txt)")

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Đánh Giá Phương Án Kinh Doanh (AI-Powered)",
    layout="wide"
)

st.title("Ứng dụng Đánh giá Phương án Kinh doanh (AI-Powered) 🚀")
st.markdown("Sử dụng Gemini AI để trích xuất dữ liệu tài chính từ file Word và tính toán hiệu quả dự án.")

# --- Helper Function: Đọc nội dung Text từ File DOCX ---
def read_docx_content(uploaded_file):
    """Sử dụng docx2txt để đọc nội dung văn bản từ file Word."""
    try:
        # docx2txt làm việc tốt với file buffer
        text = docx2txt.process(uploaded_file)
        return text
    except Exception as e:
        st.error(f"Lỗi khi đọc file Word: {e}. Vui lòng đảm bảo file là định dạng .docx hợp lệ và thư viện 'docx2txt' đã được cài đặt.")
        return None

# --- Chức năng 1: Trích xuất Dữ liệu Tài chính bằng AI (Structured Output) ---
def ai_extract_financial_data(doc_content, api_key):
    """Gửi nội dung file Word đến Gemini để trích xuất dữ liệu tài chính có cấu trúc."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'

        prompt = f"""
        Bạn là chuyên gia phân tích tài chính. Nhiệm vụ của bạn là trích xuất 6 thông số sau từ tài liệu phương án kinh doanh được cung cấp, sau đó trả về dưới định dạng JSON.
        
        Các thông số cần trích xuất:
        1. Vốn đầu tư (Investment): Tổng vốn ban đầu.
        2. Dòng đời dự án (Lifespan): Số năm dự kiến của dự án (phải là số nguyên dương).
        3. WACC (WACC): Tỷ lệ chiết khấu/chi phí vốn bình quân (dạng thập phân, ví dụ 0.10 cho 10%).
        4. Thuế suất (TaxRate): Thuế suất thuế thu nhập doanh nghiệp (dạng thập phân, ví dụ 0.20 cho 20%).
        5. Doanh thu hàng năm (Revenues): Danh sách (List) các giá trị doanh thu hàng năm theo thứ tự thời gian, bắt đầu từ Năm 1 đến hết Dòng đời dự án.
        6. Chi phí hàng năm (Costs): Danh sách (List) các giá trị chi phí hoạt động hàng năm theo thứ tự thời gian, bắt đầu từ Năm 1 đến hết Dòng đời dự án.
        
        Nội dung tài liệu:
        ---
        {doc_content}
        ---
        Lưu ý: Đảm bảo số lượng phần tử trong danh sách Doanh thu và Chi phí phải bằng Dòng đời dự án. Nếu không tìm thấy thông tin cụ thể, sử dụng giá trị ước tính hợp lý (ví dụ: WACC=0.10, TaxRate=0.20) hoặc 0 nếu là dòng tiền.
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "Investment": {"type": "NUMBER", "description": "Tổng vốn đầu tư ban đầu."},
                        "Lifespan": {"type": "INTEGER", "description": "Số năm dự án."},
                        "WACC": {"type": "NUMBER", "description": "Tỷ lệ chiết khấu (0.xx)."},
                        "TaxRate": {"type": "NUMBER", "description": "Thuế suất (0.xx)."},
                        "Revenues": {"type": "ARRAY", "items": {"type": "NUMBER"}, "description": "Doanh thu hàng năm (list)."},
                        "Costs": {"type": "ARRAY", "items": {"type": "NUMBER"}, "description": "Chi phí hàng năm (list)."}
                    },
                    "required": ["Investment", "Lifespan", "WACC", "TaxRate", "Revenues", "Costs"]
                }
            )
        )
        # Parse chuỗi JSON trả về
        return json.loads(response.text)

    except APIError as e:
        st.error(f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Lỗi giải mã JSON từ AI. Vui lòng thử lại với file đầu vào rõ ràng hơn.")
        return None
    except Exception as e:
        st.error(f"Đã xảy ra lỗi không xác định trong quá trình trích xuất AI: {e}")
        return None

# --- Chức năng 2 & 3: Xây dựng Dòng tiền và Tính toán Chỉ số ---
def calculate_project_metrics(data):
    """Xây dựng bảng dòng tiền và tính toán NPV, IRR, PP, DPP."""
    
    # 1. Chuẩn bị Dữ liệu
    Lifespan = int(data['Lifespan'])
    WACC = data['WACC']
    TaxRate = data['TaxRate']
    Investment = data['Investment']
    
    # Đảm bảo list có độ dài phù hợp
    Revenues = data['Revenues'][:Lifespan]
    Costs = data['Costs'][:Lifespan]
    
    # 2. Xây dựng Bảng Dòng tiền
    years = [f"Năm {i}" for i in range(1, Lifespan + 1)]
    df = pd.DataFrame({
        'Năm': years,
        'Doanh thu (A)': Revenues,
        'Chi phí (B)': Costs,
    })
    
    # Tính toán Lợi nhuận trước thuế (EBT)
    df['Lợi nhuận trước thuế (C=A-B)'] = df['Doanh thu (A)'] - df['Chi phí (B)']
    
    # Tính Thuế
    df['Thuế (D=C*Thuế suất)'] = df['Lợi nhuận trước thuế (C=A-B)'].apply(lambda x: max(0, x) * TaxRate)
    
    # Tính Lợi nhuận sau thuế (E)
    df['Lợi nhuận sau thuế (E=C-D)'] = df['Lợi nhuận trước thuế (C=A-B)'] - df['Thuế (D=C*Thuế suất)']
    
    # Dòng tiền thuần (Net Cash Flow - NCF): Giả định không có Khấu hao
    df['Dòng tiền thuần (NCF)'] = df['Lợi nhuận sau thuế (E=C-D)'] 
    
    # 3. Tính toán các Chỉ số
    
    # Mảng Dòng tiền (bao gồm Vốn đầu tư ban đầu ở năm 0)
    cash_flows = [-Investment] + df['Dòng tiền thuần (NCF)'].tolist()
    
    # NPV (Giá trị hiện tại ròng)
    NPV = np.npv(WACC, cash_flows)
    
    # IRR (Tỷ suất sinh lời nội bộ)
    try:
        IRR = np.irr(cash_flows)
    except ValueError:
        IRR = np.nan # Không thể tính nếu dòng tiền không đổi dấu
    
    # Cumulative Cash Flow (Dòng tiền tích lũy)
    cumulative_cf = np.cumsum(cash_flows)
    df['Dòng tiền tích lũy'] = cumulative_cf[1:]
    
    # Discounted Cash Flow (Dòng tiền chiết khấu)
    discount_factors = [1 / (1 + WACC)**i for i in range(1, Lifespan + 1)]
    df['Dòng tiền chiết khấu (DCF)'] = df['Dòng tiền thuần (NCF)'] * discount_factors
    
    # Cumulative Discounted Cash Flow (Dòng tiền chiết khấu tích lũy)
    discounted_cf_with_initial = [-Investment] + df['Dòng tiền chiết khấu (DCF)'].tolist()
    cumulative_dcf = np.cumsum(discounted_cf_with_initial)
    df['Dòng tiền chiết khấu tích lũy'] = cumulative_dcf[1:]
    
    
    # PP (Thời gian hoàn vốn)
    pp_year = (np.argmax(cumulative_cf >= 0) if (cumulative_cf >= 0).any() else Lifespan + 1)
    if pp_year <= Lifespan:
        # Interpolation
        prev_cf = cumulative_cf[pp_year - 1]
        current_ncf = cash_flows[pp_year]
        PP = (pp_year - 1) + (-prev_cf / current_ncf)
    else:
        PP = 'Không hoàn vốn'
        
    # DPP (Thời gian hoàn vốn có chiết khấu)
    dpp_year = (np.argmax(cumulative_dcf >= 0) if (cumulative_dcf >= 0).any() else Lifespan + 1)
    if dpp_year <= Lifespan:
        # Interpolation
        prev_dcf = cumulative_dcf[dpp_year - 1]
        current_dcf = discounted_cf_with_initial[dpp_year]
        DPP = (dpp_year - 1) + (-prev_dcf / current_dcf)
    else:
        DPP = 'Không hoàn vốn chiết khấu'
        
    metrics = {
        'NPV': NPV,
        'IRR': IRR,
        'PP': PP,
        'DPP': DPP,
        'WACC': WACC,
        'Lifespan': Lifespan
    }
    
    return df, metrics

# --- Chức năng 4: Phân tích Chỉ số bằng AI ---
def get_ai_evaluation(metrics, api_key):
    """Gửi các chỉ số NPV, IRR, PP, DPP đến Gemini để nhận phân tích."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'
        
        # Định dạng dữ liệu cho AI
        metrics_str = f"""
        - NPV (Giá trị hiện tại ròng): {metrics['NPV']:,.0f} VNĐ
        - IRR (Tỷ suất sinh lời nội bộ): {metrics['IRR'] * 100:.2f}%
        - WACC (Chi phí vốn): {metrics['WACC'] * 100:.2f}%
        - Thời gian hoàn vốn (PP): {metrics['PP'] if isinstance(metrics['PP'], str) else f'{metrics['PP']:.2f} năm'}
        - Thời gian hoàn vốn có chiết khấu (DPP): {metrics['DPP'] if isinstance(metrics['DPP'], str) else f'{metrics['DPP']:.2f} năm'}
        - Dòng đời dự án: {metrics['Lifespan']} năm
        """

        prompt = f"""
        Bạn là một chuyên gia thẩm định dự án đầu tư. Dựa trên các chỉ số hiệu quả dự án sau, hãy đưa ra phân tích đánh giá tính khả thi và rủi ro của phương án kinh doanh này.
        
        Phân tích cần tập trung vào:
        1. Tính khả thi (dựa trên NPV và so sánh IRR với WACC).
        2. Rủi ro và tính thanh khoản (dựa trên PP và DPP so với dòng đời dự án).
        3. Kết luận và đề xuất ngắn gọn.

        Dữ liệu Chỉ số:
        {metrics_str}
        
        Viết phân tích bằng tiếng Việt, khoảng 4-5 đoạn ngắn gọn.
        """

        with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: {e}"
    except Exception as e:
        return f"Lỗi không xác định: {e}"

# --- Logic Ứng dụng Chính ---
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None

api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

# --- Upload và Trích xuất Dữ liệu (Chức năng 1) ---
with st.sidebar:
    st.header("1. Tải File Phương Án Kinh Doanh")
    uploaded_file = st.file_uploader(
        "Vui lòng tải file Word (.docx) của phương án kinh doanh:",
        type=['docx']
    )
    
    if uploaded_file is not None and api_key:
        if st.button("Trích xuất Dữ liệu Tài chính (AI)"):
            with st.spinner('AI đang đọc và trích xuất dữ liệu từ file Word...'):
                doc_content = read_docx_content(uploaded_file)
                if doc_content:
                    extracted_data = ai_extract_financial_data(doc_content, api_key)
                    if extracted_data:
                        st.session_state.extracted_data = extracted_data
                        st.success("Trích xuất dữ liệu thành công! Tiếp tục đến bước 2.")

# --- Hiển thị và Tính toán (Chức năng 2 & 3) ---
if st.session_state.extracted_data:
    data = st.session_state.extracted_data
    st.subheader("2. Dữ liệu Tài chính Trích xuất từ AI")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vốn Đầu Tư", f"{data['Investment']:,.0f} VNĐ")
    col2.metric("Dòng Đời Dự Án", f"{data['Lifespan']} năm")
    col3.metric("WACC (Chi phí vốn)", f"{data['WACC'] * 100:.2f}%")
    col4.metric("Thuế suất", f"{data['TaxRate'] * 100:.2f}%")
    
    st.markdown("---")
    
    # Kiểm tra tính hợp lệ của list
    if len(data['Revenues']) != data['Lifespan'] or len(data['Costs']) != data['Lifespan']:
        st.warning(
            f"⚠️ Lỗi dữ liệu trích xuất: Dòng đời dự án là {data['Lifespan']} năm, nhưng AI chỉ trích xuất được {len(data['Revenues'])} giá trị Doanh thu/Chi phí. Vui lòng kiểm tra lại nội dung file Word."
        )
    
    try:
        df_cash_flow, metrics = calculate_project_metrics(data)
        
        st.subheader("3. Bảng Dòng tiền và Chỉ số Đánh giá Hiệu quả Dự án")
        
        tab1, tab2 = st.tabs(["Bảng Dòng tiền Chi tiết", "Các Chỉ số Chính"])
        
        with tab1:
            st.dataframe(df_cash_flow.style.format({
                'Doanh thu (A)': '{:,.0f}',
                'Chi phí (B)': '{:,.0f}',
                'Lợi nhuận trước thuế (C=A-B)': '{:,.0f}',
                'Thuế (D=C*Thuế suất)': '{:,.0f}',
                'Lợi nhuận sau thuế (E=C-D)': '{:,.0f}',
                'Dòng tiền thuần (NCF)': '{:,.0f}',
                'Dòng tiền tích lũy': '{:,.0f}',
                'Dòng tiền chiết khấu (DCF)': '{:,.0f}',
                'Dòng tiền chiết khấu tích lũy': '{:,.0f}',
            }), use_container_width=True)
            
        with tab2:
            st.markdown(f"**Vốn đầu tư ban đầu:** {metrics['Investment']:,.0f} VNĐ")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            
            with col_m1:
                if metrics['NPV'] > 0:
                    st.success(f"**NPV:** {metrics['NPV']:,.0f} VNĐ (Dự án khả thi)")
                else:
                    st.error(f"**NPV:** {metrics['NPV']:,.0f} VNĐ (Dự án không khả thi)")

            with col_m2:
                if metrics['IRR'] > metrics['WACC']:
                    st.success(f"**IRR:** {metrics['IRR'] * 100:.2f}% (IRR > WACC)")
                else:
                    st.error(f"**IRR:** {metrics['IRR'] * 100:.2f}% (IRR < WACC)")

            with col_m3:
                pp_value = metrics['PP']
                if isinstance(pp_value, str) or pp_value > metrics['Lifespan']:
                    st.warning(f"**PP (Hoàn vốn):** {pp_value}")
                else:
                    st.metric("PP (Hoàn vốn)", f"{pp_value:.2f} năm")

            with col_m4:
                dpp_value = metrics['DPP']
                if isinstance(dpp_value, str) or dpp_value > metrics['Lifespan']:
                    st.warning(f"**DPP (Hoàn vốn CK):** {dpp_value}")
                else:
                    st.metric("DPP (Hoàn vốn CK)", f"{dpp_value:.2f} năm")

        st.markdown("---")
        
        # --- Chức năng 4: Yêu cầu AI Phân tích ---
        st.subheader("4. Phân tích Chuyên sâu Chỉ số Dự án (AI)")
        if st.button("Yêu cầu Gemini AI Phân tích Hiệu quả"):
            ai_result = get_ai_evaluation(metrics, api_key)
            st.markdown("**Kết quả Phân tích từ Gemini AI:**")
            st.info(ai_result)

    except Exception as e:
        st.error(f"Lỗi tính toán: Không thể xử lý dữ liệu dòng tiền. Vui lòng kiểm tra dữ liệu trích xuất. Chi tiết: {e}")

else:
    st.info("Chờ đợi file được tải lên và dữ liệu được trích xuất...")
