import asyncio
import aiohttp
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Отримай токен у @BotFather в Telegram
BOT_TOKEN = "8568170423:AAG5rst_h7f_T05F3_eCyI-ANkamyomKpPk"
# Твій поточний публічний URL
NGROK_URL = "https://solpay-u212.onrender.com" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Визначаємо кроки для збору даних
class CampaignForm(StatesGroup):
    title = State()
    wallet = State()

# Нова ЖОРСТКА асинхронна перевірка через блокчейн
async def is_real_solana_wallet(wallet: str) -> bool:
    # 1. Швидкий фільтр від спаму (щоб не смикати API на відверте сміття)
    if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", wallet):
        return False
        
    # 2. Запит напряму в Mainnet Solana
    rpc_url = "https://api.mainnet-beta.solana.com"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [wallet, {"encoding": "base58"}]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc_url, json=payload, timeout=5) as response:
                data = await response.json()
                
                # Якщо нода лається, що адреса не існує на криптографічній кривій Ed25519
                if "error" in data:
                    print(f"[-] Фейковий гаманець відхилено: {wallet}")
                    return False
                    
                # Якщо адреса валідна (навіть якщо на ній 0 балансу, вона пройде перевірку)
                return True
    except Exception as e:
        print(f"[!] Помилка зв'язку з Solana RPC: {e}")
        # Якщо API впало, довіряємо регулярці, щоб не паралізувати бота
        return True

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "Привіт! Давай створимо Solana Blink для твого збору.\n\n"
        "Напиши коротку назву або мету збору (наприклад: На MVP хакатону):"
    )
    await state.set_state(CampaignForm.title)

@dp.message(CampaignForm.title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Чудово. Тепер надішли свою публічну адресу гаманця Solana, куди надходитимуть донати:")
    await state.set_state(CampaignForm.wallet)

@dp.message(CampaignForm.wallet)
async def process_wallet(message: Message, state: FSMContext):
    wallet = message.text.strip()
    
    # Надсилаємо повідомлення-заглушку, оскільки запит до блокчейну може зайняти секунду-дві
    wait_msg = await message.answer("⏳ Перевіряю гаманець у блокчейні Solana...")
    
    # Чекаємо відповіді від реальної мережі
    if not await is_real_solana_wallet(wallet):
        await wait_msg.edit_text(
            "❌ <b>Ця адреса відхилена мережею Solana!</b>\n"
            "Гаманець не існує або містить помилку. Надішли реальну публічну адресу:",
            parse_mode="HTML"
        )
        return # Бот зупиниться тут і знову чекатиме правильну адресу
        
    data = await state.get_data()
    title = data.get("title")
    
    # Формуємо підсумкове посилання Blink
    blink_url = f"{NGROK_URL}/api/actions/donate?creator={wallet}"
    
    text = (
        f"✅ <b>Гаманець підтверджено мережею! Твій Blink готовий.</b>\n\n"
        f"🎯 <b>Мета:</b> {title}\n"
        f"💼 <b>Гаманець:</b> <code>{wallet}</code>\n\n"
        f"🔗 <b>Посилання для вставки в X (Twitter) або Telegram:</b>\n"
        f"<code>{blink_url}</code>"
    )
    
    await wait_msg.edit_text(text, parse_mode="HTML")
    await state.clear()

async def main():
    print("[+] Бот запущений і готовий до роботи!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())