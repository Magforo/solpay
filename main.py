import base64
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI()

# Базові заголовки за специфікацією Solana Actions
ACTIONS_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, Content-Encoding, Accept-Encoding, X-Accept-Action-Version, X-Accept-Blockchain-Ids, ngrok-skip-browser-warning",
    "Access-Control-Expose-Headers": "X-Action-Version, X-Blockchain-Ids, ngrok-skip-browser-warning",
    "Content-Type": "application/json",
    "X-Action-Version": "2.1.3",
    "X-Blockchain-Ids": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
    "ngrok-skip-browser-warning": "69420"
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Action-Version", "X-Blockchain-Ids", "ngrok-skip-browser-warning"],
)

@app.middleware("http")
async def add_solana_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=200, headers=ACTIONS_CORS_HEADERS)

    response = await call_next(request)
    for key, value in ACTIONS_CORS_HEADERS.items():
        response.headers[key] = value
    return response

@app.get("/actions.json")
async def get_actions_json():
    return JSONResponse(content={
        "rules": [
            {
                "pathPattern": "/*",
                "apiPath": "/*"
            }
        ]
    })

# GET: приймає гаманець творця (creator) з URL
@app.get("/api/actions/donate")
async def get_action_info(creator: str = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"): # Стандартний гаманець, якщо параметр не передано
    payload = {
        "type": "action",
        "icon": "https://solana.com/src/img/branding/solanaLogoMark.png",
        "title": "Збір на перемогу в чемпіонаті",
        # Показуємо скорочений гаманець автора в описі картки
        "description": f"Підтримай розробку! Кошти будуть надіслані автору: {creator[:4]}...{creator[-4:]}",
        "label": "Підтримати",
        "links": {
            "actions": [
                {
                    "label": "0.01 SOL",
                    # Обов'язково прокидаємо creator далі в POST-запит
                    "href": f"/api/actions/donate?amount=0.01&creator={creator}"
                },
                {
                    "label": "0.05 SOL",
                    "href": f"/api/actions/donate?amount=0.05&creator={creator}"
                },
                {
                    "label": "0.1 SOL",
                    "href": f"/api/actions/donate?amount=0.1&creator={creator}"
                }
            ]
        }
    }
    return JSONResponse(content=payload)


class ActionPayload(BaseModel):
    account: str


# POST: генерує реальну транзакцію в мережі Solana
@app.post("/api/actions/donate")
async def post_action_data(payload: ActionPayload, amount: float = 0.01, creator: str = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"):
    donor_wallet = payload.account
    
    print(f"\n[+] Новий запит на транзакцію!")
    print(f"    Від кого (донор): {donor_wallet}")
    print(f"    Кому (автор збору): {creator}")
    print(f"    Сума: {amount} SOL\n")

    try:
        # 1. Переводимо адреси з тексту в криптографічні об'єкти Pubkey
        donor_pubkey = Pubkey.from_string(donor_wallet)
        creator_pubkey = Pubkey.from_string(creator)
        
        # 2. Конвертуємо SOL у мінімальні одиниці (лампорти). 1 SOL = 1 000 000 000 лампортів
        lamports = int(amount * 1_000_000_000)
        
        # 3. Створюємо системну інструкцію переказу
        ix = transfer(
            TransferParams(
                from_pubkey=donor_pubkey,
                to_pubkey=creator_pubkey,
                lamports=lamports
            )
        )
        
        # Підключаємося до Mainnet для отримання актуального blockhash 
        # (без нього транзакція вважається застарілою і мережа її відхилить)
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            blockhash_resp = await client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash
            
        # 5. Збираємо сучасну версію транзакції (VersionedTransaction)
        msg = MessageV0.try_compile(
            payer=donor_pubkey,
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )
        
        # Створюємо масив з одного порожнього підпису (заглушка для гаманця донора)
        signatures = [Signature.default()]
        
        # Використовуємо метод populate для створення непідписаної транзакції
        tx = VersionedTransaction.populate(msg, signatures)
        
        # 6. Серіалізуємо в байти та кодуємо в рядок Base64
        serialized_tx = base64.b64encode(bytes(tx)).decode('utf-8')
        
        return JSONResponse(content={
            "transaction": serialized_tx,
            "message": f"Дякуємо! Ви підтримали автора на {amount} SOL"
        })
        
    except Exception as e:
        print(f"[!] Помилка створення транзакції: {e}")
        return JSONResponse(status_code=400, content={"message": "Помилка формування транзакції"})