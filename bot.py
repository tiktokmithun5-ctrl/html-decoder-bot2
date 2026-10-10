import os, re, json, base64, html, logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_BYTES = 15 * 1024 * 1024

def js_string(raw: str) -> str:
    """Decode a quoted JavaScript string's common escapes."""
    try:
        return json.loads('"' + raw + '"')
    except Exception:
        return raw.replace(r"\u", "\\u")

def decode_habib_cipher(source: str):
    # Decoder for the specific emoji/symbol substitution + XOR/additive cipher
    # used by the uploaded sample. Only decode data; never execute the HTML/JS.
    arr_match = re.search(r'const\s+_emjList\s*=\s*(\[[\s\S]*?\]);', source)
    data_match = re.search(r'const\s+_pData\s*=\s*"((?:\\.|[^"\\])*)"\s*;', source)
    params = re.search(r'const\s+_sA\s*=\s*(\d+)\s*;\s*const\s+_sB\s*=\s*(\d+)\s*;\s*const\s+_sC\s*=\s*(\d+)', source)
    if not (arr_match and data_match and params):
        return None
    try:
        symbols = json.loads(arr_match.group(1))
        pdata = js_string(data_match.group(1))
        sa, sb, sc = map(int, params.groups())
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        mapping = {symbol: alphabet[i] for i, symbol in enumerate(symbols) if i < len(alphabet)}
        mapping["•"] = "="
        raw_b64 = "".join(mapping.get(ch, ch) for ch in pdata)
        raw_b64 += "=" * ((-len(raw_b64)) % 4)
        encrypted = base64.b64decode(raw_b64, validate=False)
        out = bytearray()
        a, b = sa, sb
        for k, value in enumerate(encrypted):
            value = (value ^ (k & 255)) & 255
            value = (value - b + 256) & 255
            value = (value ^ a) & 255
            out.append(value)
            a = (a * 3 + sc) & 255
            b = (b + 19) & 255
        return out.decode("utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Custom cipher decode failed: {exc}") from exc

def decode_file(data: bytes, filename: str) -> tuple[bytes, str]:
    text = data.decode("utf-8-sig", errors="replace")
    decoded = decode_habib_cipher(text)
    if decoded is not None:
        return decoded.encode("utf-8"), "Detected custom emoji/symbol cipher"
    # Safe, non-executing basic decoders.
    result = html.unescape(text)
    # Decode escaped unicode sequences often found in JS/HTML exports.
    if r"\u" in result or r"\x" in result:
        try:
            result = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), result)
            result = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), result)
        except Exception:
            pass
    # Decode a whole-file Base64 document if it looks like one.
    compact = re.sub(r'\s+', '', result)
    if len(compact) > 80 and re.fullmatch(r'[A-Za-z0-9+/]*={0,2}', compact):
        try:
            candidate = base64.b64decode(compact, validate=True)
            candidate_text = candidate.decode("utf-8")
            if "<html" in candidate_text.lower() or "<!doctype" in candidate_text.lower() or "<script" in candidate_text.lower():
                return candidate, "Detected Base64-encoded HTML/JavaScript"
        except Exception:
            pass
    return result.encode("utf-8"), "Applied HTML-entity / JS-escape decoding (no custom cipher detected)"

HELP = (
    "HTML Decoder Bot\\n\\n"
    "একটি .html/.htm/.js/.txt ফাইল পাঠান—আমি ডিকোড করে নতুন ফাইল ফেরত দেব।\\n"
    "Supported: HTML entities, common \\\\u/\\\\x escapes, Base64 HTML, and the matching custom symbol cipher.\\n"
    "সতর্কতা: সব obfuscation ভাঙা সম্ভব নয়। ফাইলের কোড execute করা হয় না।"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document
    if not doc:
        return
    if doc.file_size and doc.file_size > MAX_BYTES:
        await msg.reply_text("ফাইলটি ১৫ MB-এর বেশি। ছোট ফাইল পাঠান।")
        return
    name = Path(doc.file_name or "input.html").name
    if Path(name).suffix.lower() not in {".html", ".htm", ".js", ".txt", ".json"}:
        await msg.reply_text("দয়া করে .html, .htm, .js, .txt বা .json ফাইল পাঠান।")
        return
    await msg.reply_text("ফাইল পেয়েছি—ডিকোড করার চেষ্টা করছি…")
    tg_file = await context.bot.get_file(doc.file_id)
    data = await tg_file.download_as_bytearray()
    if len(data) > MAX_BYTES:
        await msg.reply_text("ফাইলটি ১৫ MB-এর বেশি।")
        return
    try:
        output, method = decode_file(bytes(data), name)
        outname = f"{Path(name).stem}_decoded{Path(name).suffix or '.html'}"
        import io
        bio = io.BytesIO(output)
        bio.name = outname
        await msg.reply_document(document=bio, caption=f"Done ✅\\nMethod: {method}\\nনোট: ফলাফল ব্রাউজারে খোলার আগে কোড দেখে নিন।")
    except Exception as exc:
        logging.exception("Decode error")
        await msg.reply_text(f"ডিকোড করা যায়নি: {str(exc)[:300]}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("কোড টেক্সট হিসেবে না পাঠিয়ে .html/.js ফাইল হিসেবে পাঠান। /help দেখুন।")

def main():
    if not TOKEN:
        raise SystemExit("Set BOT_TOKEN environment variable with your Telegram bot token.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
