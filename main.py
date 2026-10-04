import requests 

WEBHOOK_URL = "https://discord.com/api/webhooks/1556088710293098558/hnKhvZ1iZSqU1pyeLyHXswRn2jkhbk-hlnsjzJlu1QAzdqKznVOBfECkny_DlXI1ZJAI"

payload = { # pacote que vamos enviar para o discord
     "content": "Meu pau na sua mão",
     "embeds": [ # cartões organizados 
          {
               "title": " kkkk zueira te amo",
               "description": "Love u",
               "color": 5814783
          }
     ]
}

resposta = requests.post(WEBHOOK_URL, json=payload) # recebimento

print(f"Código de resposta do Discord: {resposta.status_code}") # injetar variaveis no texto
