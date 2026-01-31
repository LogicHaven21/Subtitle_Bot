import time
import pyperclip
import json
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

class GeminiBot:
    def __init__(self, port=9222):
        self.port = port
        self.driver = None
        self.active_tabs = []
        self._last_clipboard = ""

    def connect(self):
        """
        اتصال پایدار به مرورگر و شناسایی تب‌های یکتا.
        """
        try:
            options = EdgeOptions()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
            self.driver = webdriver.Edge(options=options)
            
            # گرفتن هندل‌های پنجره
            raw_handles = self.driver.window_handles
            
            # حذف تکراری‌ها با حفظ ترتیب (رفع باگ تکرار تب در داشبورد)
            # استفاده از دیکشنری برای حذف تکراری‌ها چون ترتیب در list set به هم می‌ریزد
            self.active_tabs = list(dict.fromkeys(raw_handles))
            
            if not self.active_tabs:
                return False, "هیچ تبی باز نیست!"
            
            return True, f"✅ متصل شد! تعداد تب‌های فعال و یکتا: {len(self.active_tabs)}"
        except Exception as e:
            return False, f"خطا در اتصال: {str(e)}"

    def focus_tab(self, tab_handle):
        """سوییچ ایمن به تب"""
        try:
            self.driver.switch_to.window(tab_handle)
            time.sleep(0.5) # فرصت تنفس به مرورگر
            return True
        except:
            return False

    def close_tab(self, tab_handle):
        """بستن تب خراب یا لیمیت شده."""
        try:
            self.driver.switch_to.window(tab_handle)
            self.driver.close()
            return True
        except Exception:
            return False

    def get_tab_titles(self, handles):
        """برچسب پنجره/تب‌ها را برمی‌گرداند."""
        titles = {}
        for h in handles:
            try:
                self.driver.switch_to.window(h)
                time.sleep(0.2)
                titles[h] = self.driver.title or "(بدون عنوان)"
            except Exception:
                titles[h] = "(خطا در خواندن عنوان)"
        return titles

    def kill_overlays(self):
        """
        تابع حیاتی برای پایداری:
        هرگونه منوی مزاحم (مثل Share)، پرده سیاه یا پاپ‌آپ را می‌بندد.
        این تابع جلوی ارور 'Element Click Intercepted' را می‌گیرد.
        """
        try:
            # 1. تلاش برای کلیک روی بدنه صفحه (بستن منوهای باز)
            self.driver.find_element(By.TAG_NAME, "body").click()
            
            # 2. ارسال دکمه ESC برای بستن مودال‌ها
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            
            # 3. حذف لایه‌های همپوشانی (Overlay Backdrops) اگر وجود داشته باشند
            self.driver.execute_script("""
                document.querySelectorAll('.cdk-overlay-backdrop').forEach(el => el.click());
                document.querySelectorAll('.mat-menu-panel').forEach(el => el.remove()); 
            """)
        except:
            pass

    def is_generating(self):
        """
        تشخیص هوشمند وضعیت جمنای (آیا مشغول است؟)
        """
        try:
            # دکمه توقف یا لودینگ فعال
            stop_btns = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Stop') or contains(@data-test-id, 'stop-generating')]"
            )
            if stop_btns:
                return True

            busy_labels = self.driver.find_elements(
                By.XPATH,
                "//span[contains(text(),'Generating') or contains(text(),'در حال تولید') or contains(text(),'writing')]"
            )
            if busy_labels:
                return True

            # اگر ورودی و دکمه ارسال حاضر باشند، فرض می‌کنیم آزاد است
            send_btns = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Send') or contains(@aria-label, 'ارسال') or contains(@aria-label,'Send message') or contains(@data-test-id,'send-button')]"
            )
            input_boxes = self.driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], div[role='textbox']")
            if send_btns and input_boxes:
                return False

            return True
        except:
            # در صورت شک، احتیاط می‌کنیم و می‌گوییم مشغول است
            return True

    def _stop_generation_if_needed(self):
        """تلاش برای توقف تولید در صورت گیر کردن."""
        try:
            stop_btns = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Stop') or contains(@data-test-id, 'stop-generating')]")
            if stop_btns:
                self.driver.execute_script("arguments[0].click();", stop_btns[0])
                time.sleep(1)
        except Exception:
            pass

    def reset_chat(self):
        """
        پاکسازی چت و آماده‌سازی صفحه سفید (New Chat).
        """
        try:
            self.kill_overlays() # اول محیط را تمیز کن
            
            # اگر دکمه Stop هست، اول آن را می‌زنیم تا متوقف شود
            stop_btns = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Stop')]")
            if stop_btns:
                self.driver.execute_script("arguments[0].click();", stop_btns[0])
                time.sleep(1)

            # پیدا کردن دکمه New Chat با چندین روش
            selectors = [
                "//span[text()='New chat']",
                "//div[@data-test-id='new-chat-button']",
                "//button[contains(@aria-label, 'New chat')]",
                "//span[contains(@class, 'new-chat')]",
                "//span[contains(text(),'گفتگوی جدید')]",
                "//button[contains(@data-test-id,'new-chat')]",
                "//a[@data-test-id='expanded-button' and contains(@aria-label,'New chat')]"
            ]
            
            for xpath in selectors:
                elements = self.driver.find_elements(By.XPATH, xpath)
                if elements:
                    # کلیک اجباری (Force Click) با JS
                    self.driver.execute_script("arguments[0].click();", elements[0])
                    time.sleep(2.5) # صبر حیاتی برای لود شدن صفحه جدید
                    return True
            # اگر هیچ دکمه‌ای پیدا نشد، با کلید میانبر تلاش می‌کنیم
            try:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.CONTROL, "n")
                time.sleep(2)
                return True
            except Exception:
                pass
            return False
        except:
            return False

    def ensure_fresh_chat(self, retries=3):
        """چت جدید را اطمینان می‌دهد؛ اگر پیام‌های قبلی دیده شود دوباره ریست می‌کند."""
        for _ in range(retries):
            self.reset_chat()
            time.sleep(1.5)

            # اگر پیام‌های قبلی (دکمه‌های کپی) وجود داشته باشد، دوباره تلاش می‌کنیم
            old_msgs = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label,'Copy')] | //mat-icon[@data-mat-icon-name='content_copy'] | //span[text()='content_copy'] | //button[@data-test-id='copy-button']"
            )
            if len(old_msgs) <= 1:  # 0 یا 1 (پیام من) قابل قبول است
                return True
        return False

    def toggle_temp_chat(self, wait_timeout=6):
        """کلیک روی دکمه چت موقت و انتظار برای آماده شدن ورودی."""
        try:
            btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-test-id='temp-chat-button']"))
            )
            self.driver.execute_script("arguments[0].click();", btn)
            WebDriverWait(self.driver, wait_timeout).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], div[role='textbox']")
            )
            time.sleep(0.5)
            return True
        except Exception:
            return False

    def ensure_temp_chat(self):
        """یک بار دکمه چت موقت را می‌زند تا ورودی آماده شود."""
        return self.toggle_temp_chat()

    def open_new_chat_and_wait(self, wait_timeout=8):
        """روی New chat کلیک می‌کند و منتظر می‌ماند ورودی ظاهر شود."""
        try:
            self.kill_overlays()
            new_chat_xpaths = [
                "//span[text()='New chat']/ancestor::button",
                "//button[contains(@aria-label,'New chat')]",
                "//div[@data-test-id='new-chat-button']",
                "//a[contains(@href,'/app') and .//span[text()='New chat']]",
                "//a[@data-test-id='expanded-button' and contains(@aria-label,'New chat')]"
            ]
            clicked = False;
            for xp in new_chat_xpaths:
                btns = self.driver.find_elements(By.XPATH, xp)
                if btns:
                    self.driver.execute_script("arguments[0].click();", btns[0])
                    clicked = True
                    break
            if not clicked:
                return False
            WebDriverWait(self.driver, wait_timeout).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], div[role='textbox']")
            )
            time.sleep(0.8)
            return True
        except Exception:
            return False

    def select_latest_chat_from_sidebar(self):
        """به لیست چت‌ها می‌رود و آخرین/جدیدترین مورد را انتخاب می‌کند."""
        try:
            # فرض: بالاترین آیتم جدیدترین است
            candidates = self.driver.find_elements(
                By.XPATH,
                "//nav//a[contains(@href,'/app') and contains(@href,'chat')] | //div[@role='navigation']//a[contains(@href,'/app') and contains(@href,'chat')] | //li[.//span[@data-test-id='chat-title']]/a"
            )
            if not candidates:
                # fallback: هر چیزی که در بخش Chats است
                candidates = self.driver.find_elements(By.XPATH, "//div[contains(@aria-label,'Chats')]//a")
            if not candidates:
                return False
            self.driver.execute_script("arguments[0].click();", candidates[0])
            time.sleep(0.7)
            return True
        except Exception:
            return False

    def delete_chat_thread(self):
        """حذف چت فعلی (منوی عنوان) و انتظار برای پاک شدن."""
        try:
            self.kill_overlays()

            # عنوان فعلی برای تطبیق پیام حذف
            chat_title = self.get_current_chat_title()

            # 1) باز کردن منوی عنوان (سه‌نقطه کنار عنوان چت در هدر)
            header_menu = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-test-id='actions-menu-button']"))
            )
            self.driver.execute_script("arguments[0].click();", header_menu)
            time.sleep(0.4)

            # 2) صبر برای باز شدن منو و کلیک Delete
            delete_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-test-id='delete-button'] | //div[@role='menu']//span[text()='Delete']/ancestor::button"))
            )
            self.driver.execute_script("arguments[0].click();", delete_btn)
            time.sleep(0.5)

            # 3) دیالوگ تأیید و کلیک Delete
            confirm_btn = WebDriverWait(self.driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-test-id='confirm-button'] | //button[contains(@aria-label,'Delete')] | //button[.//span[text()='Delete']]"))
            )
            self.driver.execute_script("arguments[0].click();", confirm_btn)
            time.sleep(0.6)

            # 4) انتظار برای پیام حذف یا خالی شدن چت
            start = time.time()
            while time.time() - start < 10:
                # بررسی toast حذف
                try:
                    toast = self.driver.find_elements(By.XPATH, "//div[contains(translate(text(),'DELETED','deleted'),'deleted')]")
                    if toast:
                        if chat_title:
                            txt = " ".join([t.text for t in toast]).lower()
                            if 'deleted' in txt and chat_title.lower() in txt:
                                return True
                        else:
                            return True
                except Exception:
                    pass

                # fallback: کاهش دکمه‌های کپی
                copy_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//button[contains(@aria-label,'Copy')] | //mat-icon[@data-mat-icon-name='content_copy'] | //span[text()='content_copy'] | //button[@data-test-id='copy-button'] | //span[contains(text(),'Copy')]/ancestor::button"
                )
                if len(copy_buttons) <= 1:
                    return True
                time.sleep(0.5)
            return False
        except Exception:
            return False

    def get_current_chat_title(self):
        """عنوان چت فعلی را از هدر برمی‌گرداند."""
        try:
            el = self.driver.find_element(By.XPATH, "//button[@data-test-id='actions-menu-button']//span[contains(@class,'conversation-title')]")
            return el.text.strip()
        except Exception:
            try:
                el = self.driver.find_element(By.XPATH, "//div[@class='conversation-title-container']//span[contains(@class,'conversation-title')]")
                return el.text.strip()
            except Exception:
                return None

    def delete_latest_chat_and_open_new(self):
        """جدیدترین چت در سایدبار را انتخاب، حذف، و سپس New chat را باز می‌کند."""
        # انتخاب تازه‌ترین چت
        if not self.select_latest_chat_from_sidebar():
            return False
        # حذف آن چت
        if not self.delete_chat_thread():
            return False
        # باز کردن چت جدید
        if not self.open_new_chat_and_wait():
            return False
        return True

    def is_page_ready(self):
        """چک می‌کند صفحه جمنای آماده تعامل است."""
        try:
            # وجود باکس ورودی و دکمه ارسال نشانه آماده بودن است
            send_btns = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Send') or contains(@aria-label,'ارسال') or contains(@aria-label,'Send message') or contains(@data-test-id,'send-button')]"
            )
            input_boxes = self.driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], div[role='textbox']")
            if send_btns and input_boxes:
                return True
            return False
        except Exception:
            return False

    def refresh_tab_and_wait(self, tab_handle, max_attempts=2, wait_timeout=12):
        """ریفرش تب و انتظار برای آماده شدن صفحه. در صورت شکست، False برمی‌گرداند."""
        try:
            self.driver.switch_to.window(tab_handle)
        except Exception:
            return False

        for attempt in range(max_attempts):
            try:
                self.driver.refresh()
            except WebDriverException:
                time.sleep(1)

            try:
                WebDriverWait(self.driver, wait_timeout).until(
                    lambda d: self.is_page_ready()
                )
                # یک تنفس کوتاه برای لود کامل
                time.sleep(1)
                return True
            except Exception:
                # اگر تلاش اول شکست خورد و هنوز فرصت داریم دوباره رفرش می‌کنیم
                time.sleep(1)
                continue
        return False

    def ensure_model(self, preferred_models, allow_fallback=True):
        """تلاش برای فعال کردن مدل ترجمه بر اساس اولویت کاربر (Pro / Thinking / Fast)."""
        try:
            self.kill_overlays()

            # باز کردن منوی مدل بر اساس DOM داده‌شده
            try:
                picker_btn = WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@data-test-id='bard-mode-menu-button'] | //button[contains(@data-test-id,'mode-menu-button')]"))
                )
                self.driver.execute_script("arguments[0].click();", picker_btn)
                time.sleep(0.4)
            except Exception:
                pass

            # اسکریپت جاوااسکریپت برای انتخاب مدل و تشخیص غیرفعال بودن (با تطبیق دقیق‌تر)
            script = """
                const desired = arguments[0] || [];
                const allowFallback = arguments[1];
                const normalize = (t) => (t || '').replace(/\s+/g,' ').trim().toLowerCase();

                const aliases = {
                    pro: ['pro'],
                    thinking: ['thinking'],
                    fast: ['fast']
                };

                function matchesAliasStrict(text, name){
                    const key = normalize(name);
                    const set = aliases[key] || [key];
                    const tokens = normalize(text).split(/[^a-z]+/).filter(Boolean);
                    return set.some(k => tokens.includes(k));
                }

                const currentEl = document.querySelector('[data-test-id="logo-pill-label-container"] span');
                const current = currentEl ? normalize(currentEl.innerText) : '';

                const menuItems = Array.from(document.querySelectorAll('button[role="menuitem"], button[mat-menu-item], .mat-mdc-menu-item'))
                    .map(el => ({
                        el,
                        text: normalize(el.innerText),
                        disabled: el.getAttribute('aria-disabled') === 'true' || el.className.includes('disabled')
                    }));

                for (const name of desired) {
                    if (current && matchesAliasStrict(current, name)) {
                        return { ok:true, selected:name, changed:false, tried:name, reason:'already' };
                    }
                    const target = menuItems.find(x => matchesAliasStrict(x.text, name) && !x.disabled);
                    if (target) {
                        target.el.click();
                        return { ok:true, selected:name, changed:true, tried:name, reason:'clicked' };
                    }
                }

                if (allowFallback && current) return { ok:true, selected:current, changed:false, tried:null, reason:'fallback-current' };
                return { ok:false, selected:current || null, changed:false, tried:null, reason:'none-available' };
            """

            result = self.driver.execute_script(script, preferred_models, allow_fallback)

            # اگر کلیک انجام شد، دوباره برچسب فعلی را می‌خوانیم تا اطمینان حاصل شود
            if result and result.get("changed"):
                time.sleep(0.8)
                try:
                    label = self.driver.find_element(By.XPATH, "//div[@data-test-id='logo-pill-label-container']/span")
                    current_label = label.text.strip().lower()
                    expected = (result.get("selected") or "").strip().lower()
                    # تأیید تطبیق دقیق با توکن
                    expected_token = expected.split()[0] if expected else ""
                    tokens = current_label.split()
                    if expected_token not in tokens:
                        return False, f"MODEL_MISMATCH: expected {expected} got {current_label}"
                except Exception:
                    return False, "MODEL_VERIFY_FAILED"

            return result.get("ok", False), result.get("selected") or "UNKNOWN"
        except Exception as e:
            return False, f"MODEL_ERROR: {str(e)}"

    def start_generation_task(self, prompt, subtitle_content):
        """
        ارسال متن با متد 'Direct Injection' (تزریق مستقیم).
        این روش ۱۰۰٪ مشکل تایپ 'v' را حل می‌کند چون اصلاً از کیبورد استفاده نمی‌کند.
        """
        
        # 1. پاکسازی محیط
        self.kill_overlays()

        # 2. توقف اگر قبلاً در حال تولید است
        if self.is_generating():
            self._stop_generation_if_needed()
            time.sleep(0.5)
            if self.is_generating():
                return False, "BUSY_GENERATING"

        full_text = f"{prompt}\n\n{subtitle_content}"
        
        try:
            # 3. پیدا کردن باکس ورودی
            input_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true'], div[role='textbox']"))
            )
            
            # 4. تزریق متن (جراحی دقیق)
            # استفاده از JSON dumps برای هندل کردن کاراکترهای خاص و خط‌های جدید
            serialized = json.dumps(full_text)
            self.driver.execute_script("""
                const el = arguments[0];
                const payload = JSON.parse(arguments[1]);
                el.innerText = payload;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            """, input_box, serialized)
            
            time.sleep(1) # مکث کوتاه تا جمنای متن جدید را هضم کند

            # 5. بیدار کردن دکمه ارسال
            # گاهی بعد از تزریق، دکمه هنوز خاکستری است. یک اسپیس مجازی می‌زنیم.
            input_box.send_keys(" ")
            time.sleep(0.5)

            # 6. کلیک روی دکمه ارسال (Force Click)
            send_btns = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Send') or contains(@aria-label,'ارسال') or contains(@aria-label,'Send message') or contains(@data-test-id,'send-button')]"
            )
            
            if send_btns:
                self.driver.execute_script("arguments[0].click();", send_btns[-1])
                return True, "STARTED"
            else:
                # پلن B: زدن اینتر
                input_box.send_keys(Keys.ENTER)
                return True, "STARTED"

        except Exception as e:
            return False, f"Start Error: {str(e)}"

    def check_is_done_and_fetch(self):
        """
        بررسی وضعیت، انتظار برای پایان، و کپی امن نتیجه.
        """
        try:
            self.kill_overlays() # پاکسازی محیط

            # اگر هنوز مشغول است، صبر کن
            if self.is_generating():
                return None, "WAITING"

            # بررسی ارور لیمیت اکانت
            if "limit reached" in self.driver.page_source.lower():
                return None, "LIMIT_ERROR"

            # شمارش دکمه‌های کپی
            # باید حداقل ۲ تا باشد (پیام من + پیام هوش مصنوعی)
            copy_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label,'Copy')] | //mat-icon[@data-mat-icon-name='content_copy'] | //span[text()='content_copy'] | //button[@data-test-id='copy-button'] | //span[contains(text(),'Copy')]/ancestor::button"
            )
            
            if len(copy_buttons) < 2:
                return None, "WAITING"

            # آخرین دکمه کپی مال آخرین جواب است
            target_btn = copy_buttons[-1]
            
            # --- عملیات کپی امن ---
            pyperclip.copy("") # 1. خالی کردن کلیپ‌بورد
            
            # 2. کلیک روی دکمه کپی
            self.driver.execute_script("arguments[0].click();", target_btn)
            
            # 3. حلقه انتظار برای پر شدن کلیپ‌بورد و پایدار شدن متن
            start_wait = time.time()
            content = ""
            stable_reads = 0
            last_read = None
            while time.time() - start_wait < 8: # تا 8 ثانیه صبر می‌کند
                content = pyperclip.paste()
                if content and len(content) > 10 and content != self._last_clipboard:
                    if content == last_read:
                        stable_reads += 1
                    else:
                        stable_reads = 1
                    last_read = content
                    if stable_reads >= 2: # دو بار خواندن یکسان = پایدار
                        break
                time.sleep(0.4)
            
            # 4. تلاش مجدد (اگر بار اول نگرفت یا متن تکراری بود)
            if not content or content == self._last_clipboard:
                self.driver.execute_script("arguments[0].click();", target_btn)
                time.sleep(1)
                retry_content = pyperclip.paste()
                if retry_content and len(retry_content) > 10:
                    content = retry_content

            # 5. بررسی محتوا
            if content and content != self._last_clipboard:
                # اگر هوش مصنوعی رد کرده باشد
                if "I cannot translate" in content: return None, "AI_REFUSAL"
                self._last_clipboard = content
                return content, "SUCCESS"
            
            return None, "WAITING"

        except Exception as e:
            return None, "WAITING"