from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import os
import math

# ========================== KONFIGURASI ============================
ALLOWED_USERS = [7372556181]  # Ganti dengan user ID kamu
BOT_TOKEN = '8103956680:AAEFoanjItDI42Viw7HGEh1z25SW8cqUDWE'

# Variabel global sementara
user_data = {}
VCF_PER_FILE = 50
NAMA_FILE_PREFIX = 'KONTAK'

# ======================= STEP STATES ===============================
ASK_PREFIX, ASK_PER_FILE, ASK_FILENAME = range(3)

# ====================== UTILITAS FORMAT NOMOR =======================
def format_nomor(nomor: str) -> str:
    nomor = nomor.strip().replace(" ", "").replace("-", "")
    if nomor.startswith('+62'):
        return nomor
    elif nomor.startswith('62'):
        return f'+{nomor}'
    elif nomor.startswith('0'):
        return f'+62{nomor[1:]}'
    else:
        return f'+62{nomor}'

# ======================== HANDLERS =================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Maaf, kamu tidak diizinkan menggunakan bot ini 🙏")
        return

    keyboard = [
        [InlineKeyboardButton(".txt ke .vcf", callback_data='convert')],
        [InlineKeyboardButton("Bantuan", callback_data='help')],
        [InlineKeyboardButton("Clear Cache", callback_data='clear')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Selamat datang! Pilih menu:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'convert':
        await query.edit_message_text("Kirim file .txt yang berisi daftar nomor HP. Setelah selesai, ketik /done")
    elif query.data == 'help':
        await query.edit_message_text("📌 Kirim file .txt berisi nomor HP (satu per baris). Setelah upload, ketik /done dan ikuti instruksi.")
    elif query.data == 'clear':
        user_data.pop(update.effective_user.id, None)
        await query.edit_message_text("✅ Cache kamu sudah dibersihkan.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document

    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Hanya file .txt yang didukung!")
        return

    file_path = f"temp_{user_id}.txt"
    file = await document.get_file()
    await file.download_to_drive(file_path)
    user_data[user_id] = {'file': file_path}
    await update.message.reply_text("✅ File diterima. Jika sudah upload semua, ketik /done untuk lanjut.")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data or 'file' not in user_data[user_id]:
        await update.message.reply_text("❌ Belum ada file yang dikirim. Kirim file .txt dulu ya!")
        return ConversationHandler.END

    await update.message.reply_text("Masukkan prefix nama kontak (contoh: CLIENT)")
    return ASK_PREFIX

async def ask_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]['prefix'] = update.message.text.upper()
    await update.message.reply_text("Berapa jumlah kontak per file? (contoh: 50)")
    return ASK_PER_FILE

async def ask_per_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        jumlah = int(update.message.text)
        user_data[user_id]['per_file'] = jumlah
        await update.message.reply_text("Masukkan nama file output (tanpa .vcf), contoh: KONTAK")
        return ASK_FILENAME
    except ValueError:
        await update.message.reply_text("❌ Format salah! Masukkan angka saja.")
        return ASK_PER_FILE

async def ask_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]['filename'] = update.message.text.upper()
    info = user_data[user_id]

    # Mulai konversi
    with open(info['file'], 'r') as f:
        lines = [format_nomor(l) for l in f if l.strip()]

    total = len(lines)
    parts = math.ceil(total / info['per_file'])
    await update.message.reply_text(f"📋 Total nomor: {total}\n📁 Jumlah file: {parts}\nMulai konversi...")

    vcf_files = []
    for i in range(parts):
        start = i * info['per_file']
        end = start + info['per_file']
        batch = lines[start:end]
        vcf_content = ""

        for j, number in enumerate(batch):
            name = f"{info['prefix']} {start + j + 1}"
            vcf_content += f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL;TYPE=CELL:{number}\nEND:VCARD\n"

        output_filename = f"{info['filename']}{i+1:03}.vcf"
        with open(output_filename, 'w') as f:
            f.write(vcf_content)
        vcf_files.append(output_filename)

    for file in vcf_files:
        await update.message.reply_document(document=open(file, 'rb'))

    os.remove(info['file'])
    for file in vcf_files:
        os.remove(file)

    await update.message.reply_text("✅ Konversi selesai dan file dikirim!")
    user_data.pop(user_id, None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Dibatalkan.")
    return ConversationHandler.END

# =========================== MAIN ==============================
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("done", done)],
        states={
            ASK_PREFIX: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_prefix)],
            ASK_PER_FILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_per_file)],
            ASK_FILENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_filename)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))


    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text("Ketik /start untuk mulai.")))
    app.add_handler(MessageHandler(filters.COMMAND, lambda u, c: u.message.reply_text("Perintah tidak dikenal. Ketik /start untuk bantuan.")))
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: None))
    app.add_handler(CommandHandler("clear", button_handler))
    app.add_handler(CommandHandler("help", button_handler))
    app.add_handler(CommandHandler("convert", button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.ALL, lambda u, c: None))
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: None))
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE, lambda u, c: None))
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: None))

    app.add_handler(CommandHandler("help", button_handler))
    app.add_handler(CommandHandler("clear", button_handler))
    app.add_handler(CommandHandler("convert", button_handler))

    print("🤖 Bot jalan...")
    app.run_polling()
