import streamlit as st
import os
import time
import uuid
from bot_engine import GeminiBot
from utils import smart_save_file, read_subtitle
from utils import is_already_translated

# --- تنظیمات صفحه (Page Config) ---
st.set_page_config(
    page_title="Taha Subtitle Bot Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- استایل CSS (طراحی تازه) ---
st.markdown("""
<style>
    :root {
        --bg: #0f172a;
        --panel: rgba(255,255,255,0.04);
        --card: rgba(255,255,255,0.06);
        --border: rgba(255,255,255,0.08);
        --text: #e5e7eb;
        --muted: #9ca3af;
        --accent: #10b981;
        --accent-2: #f59e0b;
        --danger: #ef4444;
    }

    .main {
        direction: rtl;
        font-family: 'Tahoma', sans-serif;
        color: var(--text);
        background: radial-gradient(circle at 20% 20%, rgba(16,185,129,0.08), transparent 25%),
                    radial-gradient(circle at 80% 0%, rgba(245,158,11,0.1), transparent 28%),
                    linear-gradient(135deg, #0b1224 0%, #0f172a 60%, #0b1323 100%);
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* ورودی‌ها */
    .stTextInput input, .stTextArea textarea {
        text-align: right;
        direction: rtl;
        background: var(--panel);
        border: 1px solid var(--border);
        color: var(--text);
    }

    /* کارت وضعیت تب‌ها */
    .status-card {
        padding: 14px;
        margin-bottom: 10px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--card);
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
        backdrop-filter: blur(6px);
        transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    }
    .status-card:hover {
        transform: translateY(-3px);
        border-color: rgba(16,185,129,0.6);
        box-shadow: 0 14px 40px rgba(16,185,129,0.18);
    }

    .working { border-right: 6px solid #38bdf8; background: rgba(56,189,248,0.08); }
    .idle { border-right: 6px solid var(--accent); background: rgba(16,185,129,0.08); }
    .dead { border-right: 6px solid var(--danger); background: rgba(239,68,68,0.08); }
    .waiting { border-right: 6px solid var(--accent-2); background: rgba(245,158,11,0.08); }

    .card-title {
        font-weight: 700;
        font-size: 1.05em;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        color: var(--text);
    }
    .card-file { font-size: 0.9em; color: var(--muted); word-break: break-all; }
    .card-status { font-size: 0.8em; padding: 3px 10px; border-radius: 12px; background: rgba(255,255,255,0.1); color: var(--text); }

    /* سایدبار */
    section[data-testid="stSidebar"] {
        background: #0b1224;
        border-left: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
    }

    /* دکمه اصلی */
    .stButton > button[kind="primary"], .stButton > button[data-baseweb] {
        border-radius: 10px;
        border: none;
        background: linear-gradient(90deg, #10b981, #0ea5e9);
        color: #0b1224;
        font-weight: 700;
        box-shadow: 0 10px 25px rgba(14,165,233,0.35);
    }

    /* تقسیم‌گر */
    hr { border: none; border-top: 1px solid var(--border); }
</style>
""", unsafe_allow_html=True)

# --- هدر اصلی ---
st.title("🤖 ربات هوشمند ترجمه (نسخه صنعتی)")
st.caption("سیستم تمام‌اتوماتیک با قابلیت ترمیم خطا و مدیریت صف پایدار")
st.divider()

# --- سایدبار: پنل کنترل ---
with st.sidebar:
    st.header("🔌 پنل اتصال")
    port = st.text_input("پورت دیباگ", "9222", help="پورتی که مرورگر با آن باز شده است")
    
    if st.button("بررسی و اتصال مجدد", type="primary"):
        bot = GeminiBot(port)
        ok, msg = bot.connect()
        if ok:
            st.toast(msg, icon="✅")
            st.success("اتصال برقرار شد")
            st.session_state['bot_instance'] = bot
            # ذخیره لیست تب‌ها به صورت یکتا (Anti-Duplication)
            st.session_state['active_tabs_list'] = list(dict.fromkeys(bot.active_tabs))
            # عناوین تب‌ها
            st.session_state['tab_titles'] = bot.get_tab_titles(st.session_state['active_tabs_list'])
            st.session_state['allowed_tabs'] = st.session_state['active_tabs_list'][:]
            st.session_state['connected'] = True
        else:
            st.error(msg)
            st.session_state['connected'] = False
            
    st.markdown("---")
    st.info("💡 **نکته:** برای پایداری بیشتر، پنجره مرورگر را در مانیتور باز نگه دارید و مینیمایز نکنید.")

    st.markdown("---")
    st.header("🪟 تب‌های فعال")
    if st.session_state.get('connected'):
        if st.button("🔄 بروزرسانی تب‌ها"):
            bot = st.session_state['bot_instance']
            ok, _ = bot.connect()
            if ok:
                st.session_state['active_tabs_list'] = list(dict.fromkeys(bot.active_tabs))
                st.session_state['tab_titles'] = bot.get_tab_titles(st.session_state['active_tabs_list'])
                st.session_state['allowed_tabs'] = st.session_state['active_tabs_list'][:]
        titles_map = st.session_state.get('tab_titles', {})
        labels = [f"Tab {i+1} — {titles_map.get(h, '(بدون عنوان)')}" for i, h in enumerate(st.session_state.get('active_tabs_list', []))]
        handles = st.session_state.get('active_tabs_list', [])
        preselected = st.session_state.get('allowed_tabs', handles)
        selection = st.multiselect("انتخاب تب‌های مجاز", options=list(zip(labels, handles)), format_func=lambda x: x[0], default=[(f"Tab {i+1} — {titles_map.get(h, '(بدون عنوان)')}", h) for h in preselected], label_visibility="collapsed")
        # استخراج هندل‌ها از انتخاب
        st.session_state['allowed_tabs'] = [h for (_, h) in selection]

    st.markdown("---")
    st.header("🧠 مدل هوش مصنوعی")
    model_options = ["Pro", "Thinking", "Fast"]
    primary_model = st.selectbox("مدل اصلی", model_options, index=0)
    fallback_enabled = st.checkbox("اگر مدل اصلی دردسترس نبود، از مدل جایگزین استفاده شود", value=True)
    fallback_models = st.multiselect(
        "ترتیب مدل‌های جایگزین",
        [m for m in model_options if m != primary_model],
        default=[m for m in model_options if m != primary_model],
        help="به ترتیب انتخاب می‌شوند."
    )

    st.markdown("---")
    st.header("🛡️ ایمنی خروجی")
    anti_mix_enabled = st.checkbox("جلوگیری از جابجایی پاسخ‌ها (توکن‌گذاری و اعتبارسنجی)", value=True)

    st.markdown("---")
    st.header("♻️ رفرش خودکار تب")
    refresh_every = st.number_input("بعد از چند فایل رفرش شود؟ (0 = هرگز)", min_value=0, value=0, step=1)
    refresh_wait = st.number_input("زمان انتظار بعد رفرش (ثانیه)", min_value=5, value=12, step=1)
    refresh_attempts = st.number_input("حداکثر تعداد رفرش مجدد در صورت شکست", min_value=1, max_value=3, value=2, step=1)

    st.markdown("---")
    st.header("⏱️ انتظار پاسخ")
    wait_timeout_minutes = st.number_input("اگر پاسخی در این مدت نیامد، تب رفرش و فایل دوباره ارسال شود (دقیقه، 0 = غیرفعال)", min_value=0.0, value=4.0, step=0.5)

    st.markdown("---")
    st.header("🧪 چت موقت (Temporary Chat)")
    use_temp_chat = st.checkbox("استفاده از چت موقت به جای New chat", value=False, help="در هر فایل، قبل از ارسال و بعد از اتمام، دکمه چت موقت زده می‌شود.")

# --- بدنه اصلی: ورودی‌ها ---
c1, c2 = st.columns(2)
with c1:
    input_dir = st.text_input("📂 پوشه ورودی (SRT انگلیسی)")
    output_dir = st.text_input("📂 پوشه خروجی (فارسی)")

with c2:
    default_prompt = """Translate this SRT subtitle to Persian. Keep the exact SRT format (numbers and timestamps). Do not add explanations. Output ONLY the translated content."""
    prompt = st.text_area("📝 پرامپت سیستم", value=default_prompt, height=100)

st.divider()

col_btn, col_status = st.columns([1, 4])
with col_btn:
    start_btn = st.button("🚀 شروع/ادامه عملیات", type="primary", use_container_width=True)
    pause_btn = st.button("⏸️ توقف موقت", use_container_width=True)
    resume_btn = st.button("▶️ ادامه از توقف", use_container_width=True)

if pause_btn:
    st.session_state['pause_requested'] = True
if resume_btn:
    st.session_state['resume_requested'] = True
    st.session_state['pause_requested'] = False

status_container = st.empty() # محل نمایش وضعیت زنده

# --- منطق اصلی (The Core Logic) ---
start_trigger = start_btn or st.session_state.get('resume_requested', False)
if st.session_state.get('resume_requested') and 'saved_state' not in st.session_state:
    st.warning("⚠️ وضعیتی برای ادامه یافت نشد. ابتدا شروع را بزنید.")
    st.session_state['resume_requested'] = False
if start_trigger:
    st.session_state['resume_requested'] = False
    if start_btn:
        st.session_state.pop('saved_state', None)
    # اگر حالت توقف ذخیره شده داریم و قصد ادامه داریم، وضعیت قبلی را بارگذاری می‌کنیم
    saved_state = st.session_state.get('saved_state') if not start_btn else None

    # 1. چک‌های امنیتی
    if 'connected' not in st.session_state or not st.session_state['connected']:
        st.error("❌ ربات متصل نیست! لطفاً از منوی سمت راست وصل شوید.")
        st.stop()
    
    if not input_dir or not output_dir:
        st.error("❌ مسیر پوشه‌ها وارد نشده است.")
        st.stop()
    
    # بازیابی ربات
    bot = st.session_state['bot_instance']

    # اطمینان از به روز بودن تب‌ها
    if not bot.active_tabs:
        # تلاش مجدد مخفی برای اتصال اگر تب‌ها پریده باشند
        bot.connect()

    # استفاده از لیست تب‌های ذخیره شده در سشن برای جلوگیری از پرش و فیلتر تب‌های مجاز
    all_tabs = st.session_state.get('active_tabs_list', bot.active_tabs)
    allowed_tabs = st.session_state.get('allowed_tabs', all_tabs)
    # حفظ ترتیب و حذف تب‌هایی که دیگر وجود ندارند
    tabs = [t for t in all_tabs if t in allowed_tabs]

    if not tabs:
        st.error("❌ هیچ تبی شناسایی نشد. لطفاً مرورگر را چک کنید.")
        st.stop()

    # ترتیب انتخاب مدل
    model_order = [primary_model] + [m for m in fallback_models if m != primary_model]
    if not fallback_enabled:
        model_order = [primary_model]

    # اگر ذخیره شده داشتیم، از همان ادامه بده
    if saved_state:
        files_queue = saved_state['files_queue']
        tab_states = saved_state['tab_states']
        dead_tabs = saved_state['dead_tabs']
        tabs = saved_state['tabs']
        processed_count = saved_state['processed_count']
        total_files = saved_state['total_files']
        skipped_translated = saved_state.get('skipped_translated', 0)
        progress_bar = st.progress(min(processed_count / total_files, 1.0))
        st.info(f"▶️ ادامه از توقف: {processed_count}/{total_files} فایل")
    else:
        # 2. اسکن فایل‌ها (رد کردن فایل‌های ترجمه‌شده موجود در خروجی)
        files_queue = []
        skipped_translated = 0
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if not file.lower().endswith(".srt"):
                    continue
                full_path = os.path.join(root, file)
                if is_already_translated(full_path, output_dir, input_dir):
                    skipped_translated += 1
                    continue
                files_queue.append(full_path)

        if not files_queue:
            st.warning("⚠️ هیچ فایل زیرنویسی جدید برای ترجمه پیدا نشد (همه ترجمه شده‌اند یا وجود ندارند).")
            st.stop()

        if skipped_translated:
            st.info(f"ℹ️ {skipped_translated} فایل که نسخه FA داشتند رد شدند.")

        total_files = len(files_queue)
        processed_count = 0
        
        # 3. جدول وضعیت (State Table)
        # IDLE: آماده کار | WORKING: در حال ترجمه | DEAD: اکانت لیمیت شده
        tab_states = {t: {'status': 'IDLE', 'file': None, 'start_time': 0, 'done_since_refresh': 0, 'token': None} for t in tabs}
        dead_tabs = []

        progress_bar = st.progress(0)
        st.info(f"✅ شروع پردازش {total_files} فایل با {len(tabs)} تب فعال...")

    # 4. حلقه اصلی (Infinite Loop until done)
    tabs_to_remove = []

    while processed_count < total_files:
        
        # توقف موقت در صورت درخواست کاربر
        if st.session_state.get('pause_requested'):
            st.session_state['saved_state'] = {
                'files_queue': files_queue,
                'tab_states': tab_states,
                'dead_tabs': dead_tabs,
                'tabs': tabs,
                'processed_count': processed_count,
                'total_files': total_files,
                'skipped_translated': skipped_translated,
            }
            st.session_state['pause_requested'] = False
            st.info("⏸️ عملیات متوقف شد. برای ادامه دکمه ادامه را بزنید.")
            st.stop()

        # --- فاز ۱: توزیع کار (Assign) ---
        for tab_handle in tabs:
            # از تب‌های مرده یا مشغول رد می‌شویم
            if tab_handle in dead_tabs: continue
            if tab_states[tab_handle]['status'] != 'IDLE': continue
            if not files_queue: continue # اگر کاری نمانده
            
            # برداشتن فایل از صف
            current_file = files_queue.pop(0)
            file_name = os.path.basename(current_file)
            
            # آماده‌سازی تب
            bot.focus_tab(tab_handle)
            
            # آماده‌سازی کانال گفتگو (چت موقت یا New chat)
            prepared = bot.ensure_temp_chat() if use_temp_chat else bot.ensure_fresh_chat()
            if not prepared:
                files_queue.insert(0, current_file)
                continue

            ok_model, selected_model = bot.ensure_model(model_order, allow_fallback=fallback_enabled)
            if not ok_model:
                st.toast(f"⛔ مدل در این تب در دسترس نیست ({file_name})", icon="⚠️")
                files_queue.insert(0, current_file)
                dead_tabs.append(tab_handle)
                tab_states[tab_handle]['status'] = 'DEAD'
                tabs_to_remove.append(tab_handle)
                continue
            if selected_model and selected_model != primary_model:
                st.toast(f"ℹ️ تب {tabs.index(tab_handle)+1} به مدل جایگزین {selected_model} سوییچ شد", icon="ℹ️")
            
            content = read_subtitle(current_file)
            if not content:
                st.toast(f"❌ فایل خراب: {file_name}")
                processed_count += 1 # فایل خراب را رد می‌کنیم که گیر نکند
                continue

            prompt_with_token = prompt
            token = None
            if anti_mix_enabled:
                # توکن یکتا برای جلوگیری از جابجایی خروجی بین تب‌ها
                token = uuid.uuid4().hex
                token_instruction = f"\n\nAfter the full SRT translation, append a final line exactly as ###TOKEN:{token}. Do not change SRT numbering or timestamps. Place the token after all subtitle lines."  # noqa: E501
                prompt_with_token = prompt + token_instruction

            # ارسال دستور (Direct Injection)
            ok, msg = bot.start_generation_task(prompt_with_token, content)
            
            if ok:
                tab_states[tab_handle]['status'] = 'WORKING'
                tab_states[tab_handle]['file'] = current_file
                tab_states[tab_handle]['start_time'] = time.time()
                tab_states[tab_handle]['token'] = token
            else:
                # اگر خطا داد، فایل برمی‌گردد به اول صف
                files_queue.insert(0, current_file)
                if msg != "BUSY_GENERATING":
                    st.toast(f"⚠️ خطای ارسال در تب: {msg}")

            # وقفه کوتاه برای جلوگیری از هنگ مرورگر
            time.sleep(1.5)

        # --- فاز ۲: بررسی و دریافت (Check & Fetch) ---
        active_workers = 0
        for tab_handle in tabs:
            if tab_handle in dead_tabs: continue
            
            if tab_states[tab_handle]['status'] == 'WORKING':
                active_workers += 1

                # تایم‌اوت پاسخ و رفرش تب در صورت نیاز
                if wait_timeout_minutes > 0:
                    elapsed = time.time() - tab_states[tab_handle]['start_time']
                    if elapsed >= wait_timeout_minutes * 60:
                        current_file = tab_states[tab_handle]['file']
                        file_name = os.path.basename(current_file) if current_file else "---"
                        st.toast(f"⏱️ تب {tabs.index(tab_handle)+1} پاسخی نداد؛ رفرش و ارسال مجدد: {file_name}", icon="⏳")

                        ok_ready = bot.refresh_tab_and_wait(tab_handle, max_attempts=int(refresh_attempts), wait_timeout=int(refresh_wait))
                        if ok_ready:
                            if use_temp_chat:
                                bot.toggle_temp_chat()
                            else:
                                bot.ensure_fresh_chat()
                            # بازگرداندن فایل به صف برای ارسال دوباره
                            if current_file:
                                files_queue.insert(0, current_file)
                        else:
                            st.toast(f"⛔ تب {tabs.index(tab_handle)+1} بعد از تایم‌اوت آماده نشد و از مدار خارج شد.", icon="💀")
                            dead_tabs.append(tab_handle)
                            tab_states[tab_handle]['status'] = 'DEAD'
                            tabs_to_remove.append(tab_handle)

                        # ریست وضعیت تب برای ادامه حلقه
                        tab_states[tab_handle]['status'] = 'IDLE'
                        tab_states[tab_handle]['file'] = None
                        tab_states[tab_handle]['token'] = None
                        tab_states[tab_handle]['start_time'] = 0
                        continue
                
                bot.focus_tab(tab_handle)
                
                # دریافت نتیجه
                result_text, status = bot.check_is_done_and_fetch()
                
                current_file = tab_states[tab_handle]['file']
                file_name = os.path.basename(current_file)

                if status == "SUCCESS":
                    expected_token = tab_states[tab_handle].get('token')
                    if anti_mix_enabled:
                        if expected_token and f"###TOKEN:{expected_token}" not in (result_text or ""):
                            # پاسخ مربوط به این کار نیست یا ناقص است
                            files_queue.insert(0, current_file)
                            tab_states[tab_handle]['status'] = 'IDLE'
                            tab_states[tab_handle]['file'] = None
                            tab_states[tab_handle]['token'] = None
                            continue

                        # پاک کردن خط توکن از خروجی
                        cleaned = []
                        for line in (result_text or "").splitlines():
                            if line.strip().startswith("###TOKEN:"):
                                continue
                            cleaned.append(line)
                        result_text = "\n".join(cleaned)

                    # موفقیت!
                    save_path, saved = smart_save_file(current_file, result_text, output_dir, input_dir)
                    
                    if saved:
                        processed_count += 1
                        progress_bar.progress(min(processed_count / total_files, 1.0))
                        st.toast(f"✅ ذخیره شد: {file_name}")
                        tab_states[tab_handle]['done_since_refresh'] += 1
                    else:
                        st.error(f"❌ خطای ذخیره‌سازی: {save_path}")
                        st.stop() # خطای هارد دیسک شوخی نیست

                    if use_temp_chat:
                        # خروج از چت موقت و آماده‌سازی برای بعدی (یک کلیک دیگر)
                        bot.toggle_temp_chat()
                        time.sleep(0.5)
                    else:
                        # حذف چت اخیر و شروع چت تازه (هوشمند بر اساس لیست چت‌ها)
                        if not bot.delete_latest_chat_and_open_new():
                            # اگر شکست خورد، حداقل یک ریست چت ساده انجام بده
                            bot.ensure_fresh_chat()
                    tab_states[tab_handle]['status'] = 'IDLE'
                    tab_states[tab_handle]['file'] = None
                    tab_states[tab_handle]['token'] = None

                    # منطق رفرش دوره‌ای تب
                    if refresh_every > 0 and tab_states[tab_handle]['done_since_refresh'] >= refresh_every:
                        ok_ready = bot.refresh_tab_and_wait(tab_handle, max_attempts=int(refresh_attempts), wait_timeout=int(refresh_wait))
                        if ok_ready:
                            tab_states[tab_handle]['done_since_refresh'] = 0
                            bot.ensure_fresh_chat()
                        else:
                            st.toast(f"⛔ تب {tabs.index(tab_handle)+1} بعد از رفرش آماده نشد و از مدار خارج شد.", icon="💀")
                            dead_tabs.append(tab_handle)
                            tab_states[tab_handle]['status'] = 'DEAD'
                            tabs_to_remove.append(tab_handle)

                elif status == "LIMIT_ERROR":
                    # لیمیت شدن اکانت
                    st.toast(f"⛔ تب {tabs.index(tab_handle)+1} لیمیت شد!", icon="💀")
                    dead_tabs.append(tab_handle)
                    tab_states[tab_handle]['status'] = 'DEAD'
                    tabs_to_remove.append(tab_handle)
                    
                    # بازگرداندن فایل به صف برای انجام توسط تب دیگر
                    if current_file:
                        files_queue.insert(0, current_file)

                elif status == "AI_REFUSAL":
                    # رد کردن ترجمه توسط هوش مصنوعی
                    st.error(f"❌ هوش مصنوعی ترجمه فایل {file_name} را رد کرد.")
                    st.stop() # توقف برای بررسی دستی
                
                # حالت WAITING: کاری نمی‌کنیم

        # --- نمایش گرافیکی وضعیت (Dashboard Update) ---
        with status_container.container():
            # ساخت HTML برای نمایش کارت‌ها
            html_content = ""
            # لوپ روی لیست تب‌های اصلی (بدون تکرار)
            for i, t in enumerate(tabs):
                state = tab_states[t]
                status = state['status']
                f_name = os.path.basename(state['file']) if state['file'] else "---"
                
                # انتخاب کلاس CSS و آیکون
                css_class = "idle"
                icon = "🟢 آماده"
                if status == 'WORKING': 
                    css_class = "working"
                    icon = "⏳ در حال ترجمه..."
                elif status == 'DEAD': 
                    css_class = "dead"
                    icon = "💀 غیرفعال (Limit)"
                
                html_content += f"""
                <div class="status-card {css_class}">
                    <div class="card-title">
                        <span>Tab {i+1}</span>
                        <span class="card-status">{icon}</span>
                    </div>
                    <div class="card-file">📂 {f_name}</div>
                </div>
                """
            st.markdown(html_content, unsafe_allow_html=True)

        # حذف تب‌های غیرفعال شده از حلقه
        if tabs_to_remove:
            for t in tabs_to_remove:
                try:
                    bot.close_tab(t)
                except Exception:
                    pass
                if t in tabs:
                    tabs.remove(t)
                    tab_states.pop(t, None)
            tabs_to_remove = []
            st.session_state['active_tabs_list'] = tabs

        # شرط خروج اضطراری: هیچ تب فعالی نداریم
        if not tabs and processed_count < total_files:
            st.error("❌ هیچ تب فعالی باقی نمانده است. عملیات متوقف شد.")
            break

        # شرط خروج اضطراری: همه اکانت‌های موجود سوخته باشند
        if tabs and len(dead_tabs) == len(tabs) and processed_count < total_files:
            st.error("❌ متاسفانه تمام اکانت‌های جمنای لیمیت شدند. عملیات متوقف شد.")
            break
        
        # اگر همه فایل‌ها تمام شد
        if processed_count == total_files:
            break
            
        # ضربان قلب سیستم (Heartbeat)
        time.sleep(2)

    if processed_count == total_files:
        st.success("🎉 عملیات با موفقیت کامل به پایان رسید! تمام فایل‌ها ترجمه شدند.")
        st.balloons()
        st.session_state.pop('saved_state', None)