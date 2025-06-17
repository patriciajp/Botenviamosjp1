import os
import json
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

# Variáveis do ambiente
TOKEN = os.environ.get("TOKEN", "7333842067:AAEynLOdFTnJeMRw-fhYhfU-UT0PFXoTduE")
ADMIN_IDS = [7968066840]
VALOR_IENE_REAL = float(os.environ.get("VALOR_IENE_REAL",0.039))
TAXA_SERVICO = float(os.environ.get("TAXA_SERVICO", 0.20))
TAXA_PIX = float(os.environ.get("TAXA_PIX", 0.0099))
CHAVE_PIX = os.environ.get("CHAVE_PIX", "pattywatanabe@outlook.com")
URL_WHATSAPP = "https://wa.me/818030734889"
URL_FORMULARIO = "https://forms.gle/SBV9vUrenLN7VELi6"
BOT_USERNAME = "@Enviamosjpbot"
GROUP_USERNAME = "@enviamos_jp"

app = ApplicationBuilder().token(TOKEN).build()

# Arquivos
ARQ_PRODUTOS = "produtos.json"
ARQ_CARRINHOS = "carrinhos.json"

# Estados
NOME_PROD, DESCRICAO, PRECO, FOTO = range(4)
NOME_CLI, SUITE, TELEFONE, EMAIL, COMPROVANTE = range(5, 10)

produtos, carrinhos, cadastro_temp = {}, {}, {}

if os.path.exists(ARQ_PRODUTOS):
    with open(ARQ_PRODUTOS) as f:
        produtos = json.load(f)

if os.path.exists(ARQ_CARRINHOS):
    with open(ARQ_CARRINHOS) as f:
        carrinhos = json.load(f)

def salvar_produtos(): json.dump(produtos, open(ARQ_PRODUTOS, "w"))
def salvar_carrinhos(): json.dump(carrinhos, open(ARQ_CARRINHOS, "w"))

# Comandos


async def ver_produtos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for pid, info in produtos.items():
        await update.message.reply_photo(
            photo=info["foto"],
            caption=f"{info['nome']}\n🇯🇵¥{info['preco']} | 🇧🇷R$ {info['preco'] * VALOR_IENE_REAL:.2f}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Comprar", url=f"https://t.me/{BOT_USERNAME}?start=prod{pid}")]])
        )

# Cadastro
async def cadastrar(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Você não tem permissão para cadastrar produtos.")
        return ConversationHandler.END
    cadastro_temp[user_id] = {}
    await update.message.reply_text(" Agora envie o *Nome do Produto*", parse_mode="Markdown")
    return NOME_PROD

async def receber_nome(update, context):
    user_id = update.effective_user.id
    cadastro_temp[user_id]['nome'] = update.message.text
    await update.message.reply_text(" Agora envie a *descrição do produto* ", parse_mode="Markdown")
    return DESCRICAO

async def receber_descricao(update, context):
    user_id = update.effective_user.id
    cadastro_temp[user_id]['descricao'] = update.message.text
    await update.message.reply_text("💰 Agora envie o *preço em ienes* (apenas números)", parse_mode="Markdown")
    return PRECO

async def receber_preco(update, context):
    user_id = update.effective_user.id
    try:
        preco = int(update.message.text)
    except ValueError:
        await update.message.reply_text("⚠️ Digite apenas números.")
        return PRECO
    cadastro_temp[user_id]['preco'] = preco
    await update.message.reply_text("📷 Agora envie a *foto do produto*", parse_mode="Markdown")
    return FOTO

async def receber_foto(update, context):
    user_id = update.effective_user.id
    foto = update.message.photo[-1].file_id
    produto = cadastro_temp[user_id]
    produto['foto'] = foto

    produto_id = str(len(produtos) + 1)
    produtos[produto_id] = produto
    salvar_produtos()

    preco_real = produto['preco'] * VALOR_IENE_REAL

    texto = (
        f"*{produto['nome']}*\n"
        f"{produto['descricao']}\n\n"
        f"🇯🇵 ¥ {produto['preco']:,}".replace(",", ".") +
        f" | 🇧🇷 R$ {preco_real:.2f}"
    )

    await context.bot.send_photo(
        chat_id=GROUP_USERNAME,
        photo=foto,
        caption=texto,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Comprar", url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=prod{produto_id}")
        ]])
    )

    await update.message.reply_text("✅ Produto cadastrado e enviado para o grupo!")
    cadastro_temp.pop(user_id, None)
    return ConversationHandler.END

async def cancelar_cadastro(update, context):
    await update.message.reply_text("❌ Cadastro cancelado.")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if context.args and context.args[0].startswith("prod"):
        pid = context.args[0][4:]
        carrinho = carrinhos.get(user_id, [])
        for i in carrinho:
            if i["id"] == pid:
                i["quantidade"] += 1
                break
        else:
            carrinho.append({"id": pid, "quantidade": 1})
        carrinhos[user_id] = carrinho
        salvar_carrinhos()
        await update.message.reply_text(
            "✅ Produto adicionado ao seu carrinho!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Ver carrinho", callback_data="ver_carrinho")]])
        )

async def ver_produtos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for pid, info in produtos.items():
        await update.message.reply_photo(
            photo=info["foto"],
            caption=f"{info['nome']}\n🇯🇵¥{info['preco']} | 🇧🇷R$ {info['preco'] * VALOR_IENE_REAL:.2f}",

            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Comprar", url=f"https://t.me/{BOT_USERNAME}?start=prod{pid}")]])
        )

def gerar_resumo(user_id):
    carrinho = carrinhos.get(str(user_id), [])
    linhas, subtotal = [], 0
    fotos = []
    for item in carrinho:
        p = produtos.get(item["id"])
        if p:
            qtd = item["quantidade"]
            total = p["preco"] * qtd
            subtotal += total
            linhas.append(f"{p['nome']} x{qtd} - ¥{total}")
            fotos.append(p["foto"])

    servico = int(subtotal * TAXA_SERVICO)
    pix = int((subtotal + servico) * TAXA_PIX)
    total = subtotal + servico + pix

    r = VALOR_IENE_REAL
    resumo = (
        "\n".join(linhas) + "\n\n" +
        f"*Subtotal:* ¥{subtotal} | R${subtotal*r:.2f}\n" +
        f"*Taxa do Serviço (20%):* ¥{servico} | R${servico*r:.2f}\n" +
        f"*Taxa do Pix (0.99%):* ¥{pix} | R${pix*r:.2f}\n" +
        f"*Total:* ¥{total} | R${total*r:.2f}"
    )
    return resumo, total, fotos

async def ver_carrinho(update, context):
                    user_id = str(update.effective_user.id)
                    if user_id not in carrinhos or not carrinhos[user_id]:
                        await (update.message or update.callback_query.message).reply_text("🛒 Seu carrinho está vazio.")
                        return

                    # Pega o objeto correto para resposta
                    target = update.message or update.callback_query.message

                    for item in carrinhos[user_id]:
                        produto = produtos.get(item["id"])
                        if produto:
                            preco_em_real = produto["preco"] * VALOR_IENE_REAL
                            texto = (
                                f"*{produto['nome']}*\n{produto['descricao']}\n\n"
                                f"Quantidade: {item['quantidade']}\n"
                                f"Total: ¥{item['quantidade'] * produto['preco']} | "
                                f"R${item['quantidade'] * preco_em_real:.2f}"
                            )

                            botoes = [
                                [
                                    InlineKeyboardButton("+1", callback_data=f"add_{item['id']}"),
                                    InlineKeyboardButton("-1", callback_data=f"sub_{item['id']}"),
                                ],
                                [InlineKeyboardButton("❌ Cancelar item", callback_data=f"del_{item['id']}")],
                                [
                                    InlineKeyboardButton("✅ Confirmar pedido", callback_data="confirmar"),
                                    InlineKeyboardButton("❌ Cancelar tudo", callback_data="cancelar_pedido"),
                                ]
                            ]

                            await target.reply_photo(
                                photo=produto["foto"],
                                caption=texto,
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup(botoes)
                            )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    # Ver carrinho
    if data == "ver_carrinho":
        await ver_carrinho(update, context)
        return ConversationHandler.END

    # Etapa 1 – mostrar resumo do pedido
    elif data == "confirmar":
        resumo, total, _ = gerar_resumo(user_id)
        await query.message.reply_text(
            f"🧾 *Resumo do pedido:*\n{resumo}\n\n"
            f"Se estiver tudo certo, confirme abaixo para finalizar o pedido.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="finalizar")],
                [InlineKeyboardButton("❌ Cancelar pedido", callback_data="cancelar_pedido")]
            ])
        )
        return ConversationHandler.END

    # Etapa 2 – iniciar fluxo de coleta de dados
    elif data == "finalizar":
        await query.message.reply_text(
            f"📝 Envie seu *nome completo* para finalizarmos o pedido.\n\n"
            f"❗ Se ainda não tem uma suíte, cadastre aqui: {URL_FORMULARIO}",
            parse_mode="Markdown"
        )
        return NOME_CLI

    # Cancelar todo o pedido
    elif data == "cancelar_pedido":
        carrinhos[user_id] = []
        salvar_carrinhos()
        await query.message.reply_text("🛑 Pedido cancelado.")
        return ConversationHandler.END

    # Ações do carrinho: +1, -1, deletar
    elif data.startswith("add_") or data.startswith("sub_") or data.startswith("del_"):
       pid = data.split("_")[1]
       carrinho = carrinhos.get(user_id, [])

       quantidade_anterior = next((i["quantidade"] for i in carrinho if i["id"] == pid), None)

       item_removido = False
       for item in carrinho:
           if item["id"] == pid:
               if data.startswith("add_"):
                   item["quantidade"] += 1
               elif data.startswith("sub_"):
                   item["quantidade"] = max(1, item["quantidade"] - 1)
               elif data.startswith("del_"):
                   carrinho.remove(item)
                   item_removido = True
               break

       carrinhos[user_id] = carrinho
       salvar_carrinhos()

       if item_removido:
           await query.message.reply_text("❌ Item removido do carrinho.")
           await query.message.delete()
           return ConversationHandler.END

       # Atualizar mensagem apenas se houve mudança
       quantidade_atual = next((i["quantidade"] for i in carrinho if i["id"] == pid), None)
       if quantidade_anterior != quantidade_atual:
           produto = produtos.get(pid)
           if produto and quantidade_atual:
               preco_em_real = produto["preco"] * VALOR_IENE_REAL
               texto = (
                   f"*{produto['nome']}*\n{produto['descricao']}\n\n"
                   f"Quantidade: {quantidade_atual}\n"
                   f"Total: ¥{quantidade_atual * produto['preco']} | R${quantidade_atual * preco_em_real:.2f}"
               )

               botoes = [
                   [
                       InlineKeyboardButton("+1", callback_data=f"add_{pid}"),
                       InlineKeyboardButton("-1", callback_data=f"sub_{pid}"),
                   ],
                   [InlineKeyboardButton("❌ Cancelar item", callback_data=f"del_{pid}")],
                   [
                       InlineKeyboardButton("✅ Confirmar pedido", callback_data="confirmar"),
                       InlineKeyboardButton("❌ Cancelar tudo", callback_data="cancelar_pedido"),
                   ]
               ]

               try:
                   await query.edit_message_caption(
                       caption=texto,
                       parse_mode="Markdown",
                       reply_markup=InlineKeyboardMarkup(botoes)
                   )
               except Exception as e:
                   print("Erro ao editar a mensagem:", e)

       return ConversationHandler.END

async def receber_nome_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nome"] = update.message.text
    await update.message.reply_text("Informe sua *suíte*", parse_mode="Markdown")
    return SUITE

async def receber_suite_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["suite"] = update.message.text
    await update.message.reply_text("Informe seu *telefone com DDD*", parse_mode="Markdown")
    return TELEFONE

async def receber_telefone_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["telefone"] = update.message.text
    await update.message.reply_text("Agora envie seu *e-mail*", parse_mode="Markdown")
    return EMAIL

async def receber_email_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["email"] = update.message.text

        await update.message.reply_text(
            "💳 *Pagamento via Pix*\n"
            f"🔑 Chave: `{CHAVE_PIX}`\n\n"
            "📸 *Após o pagamento, envie o comprovante aqui mesmo no chat para darmos continuidade ao processo.*\n\n"
            "💳 *Quer parcelar no cartão?*\n"
            "Entre em contato para receber o link de pagamento com opções de parcelamento 💳\n"
            "_(Taxa de 4,99% será adicionada)_\n\n"
            f"❓ *Dúvidas?* Chame no WhatsApp: {URL_WHATSAPP}",
            parse_mode="Markdown"
    )
        return COMPROVANTE

async def receber_comprovante(update: Update, context: ContextTypes.DEFAULT_TYPE):
       user_id = str(update.effective_user.id)
       if not update.message.photo:
           await update.message.reply_text("⚠️ Por favor, envie uma *foto* do comprovante.")
           return COMPROVANTE

       comprovante_foto = update.message.photo[-1].file_id
       resumo, total, fotos = gerar_resumo(user_id)

       msg = f"📦 *Novo pedido de {context.user_data['nome']}*\n\n"
       msg += f"• Suíte: {context.user_data['suite']}\n"
       msg += f"• Tel: {context.user_data['telefone']}\n"
       msg += f"• E-mail: {context.user_data['email']}\n\n"
       msg += f"🧾 *Resumo:*\n{resumo}"

       for admin_id in ADMIN_IDS:
           await context.bot.send_message(chat_id=admin_id, text=msg, parse_mode="Markdown")
           for foto in fotos:
               await context.bot.send_photo(chat_id=admin_id, photo=foto)
           await context.bot.send_photo(chat_id=admin_id, photo=comprovante_foto, caption="📸 *Comprovante de pagamento*", parse_mode="Markdown")

       await update.message.reply_text(
           "✅ Pedido finalizado com sucesso!\n\n"
           "🧾 Aguardaremos a confirmação e daremos continuidade ao processo.",
           parse_mode="Markdown"
       )

       carrinhos[user_id] = []
       salvar_carrinhos()
       return ConversationHandler.END

async def cancelar(update, context):
    await update.message.reply_text("❌ Cadastro cancelado.")
    return ConversationHandler.END

def configurar_handlers():
      
       app.add_handler(CommandHandler("start", start))
       app.add_handler(CommandHandler("produtos", ver_produtos))

       # Botões carrinho
       app.add_handler(CallbackQueryHandler(callback_handler, pattern="^(ver_carrinho|add_.*|sub_.*|del_.*|cancelar_pedido|confirmar)$"))

       # Pedido
       app.add_handler(ConversationHandler(
           entry_points=[CallbackQueryHandler(callback_handler, pattern="^(confirmar|finalizar)$")],
           states={
               NOME_CLI: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome_cliente)],
               SUITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_suite_cliente)],
               TELEFONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_telefone_cliente)],
               EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email_cliente)],
               COMPROVANTE: [MessageHandler(filters.PHOTO, receber_comprovante)],
           },
           fallbacks=[CommandHandler("cancelar", cancelar)]
       ))

       # Cadastro de produtos
       app.add_handler(ConversationHandler(
           entry_points=[CommandHandler("cadastrar", cadastrar)],
           states={
               NOME_PROD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)],
               DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
               PRECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_preco)],
               FOTO: [MessageHandler(filters.PHOTO, receber_foto)],
           },
           fallbacks=[CommandHandler("cancelar", cancelar_cadastro)],
       ))


# Servidor Flask para manter o bot online no Render
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "✅ Bot Enviamos JP está funcionando!", 200

@app_flask.route('/healthz')
def healthz():
    return "OK", 200

def manter_online():
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    

async def main():
    manter_online()
    configurar_handlers()
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())