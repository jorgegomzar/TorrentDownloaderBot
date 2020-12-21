import config, logging, time
from qbittorrent import Client
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import Updater, CommandHandler
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.ext.conversationhandler import ConversationHandler

### Config inicial
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
torrent_link, save_path = '',''
TYPE, MAGNET, CONFIRM = range(3)

### Funciones
def start(update: Update, context: CallbackContext) -> int:
	"""
	Respuesta al comando "/start"
	- Comprueba la ID para saber si es un usuario permitido
		- Si lo es, pregunta por el tipo de media
		- Si no lo es, finaliza la conversación y exporta en logs info adicional
	"""
	global torrent_link, save_path
	torrent_link, save_path = '',''

	reply_keyboard = [config.ALLOWED_TYPES]

	if update.effective_chat.id not in config.ALLOWED_IDS:
		logger.info('⚠️- Un usuario SIN permiso ha intentado usar el bot')
		logger.info('Chat ID: ' + update.effective_chat.id)
		logger.info('Usuario: ' + update.effective_chat.first_name + ' ' + update.effective_chat.last_name)
		logger.info('Bio: ' + update.effective_chat.bio)
		update.message.reply_text(
			'❌ No tengo permiso para hablar contigo'
		)
		return ConversationHandler.END
	else:
		logger.info('ℹ - Un usuario CON permiso solicita usar el bot')
		update.message.reply_text(
			'Hola, ¿qué tipo de media vamos a descargar?\n'
			'Escribe /cancel para cancelar el proceso',
			reply_markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
		)
		return TYPE

def type(update: Update, context: CallbackContext) -> int:
	"""
	Respuesta al tipo de media
	- Se establece la ubicacion para guardar la descarga
	- Se le pide al usuario el magnet URL del torrent
	"""
	type = update.message.text
	global save_path
	save_path = config.SAVE_PATH + type

	logger.info(' [-] Tipo: {}'.format(type.upper()))
	logger.info(' [-] Save path: {}'.format(save_path))
	update.message.reply_text(
			'De acuerdo, vamos a descargar un torrent de tipo "'+type.upper()+'"\n'
			'A continuación, pásame el magnet URL del torrent',
			reply_markup=ReplyKeyboardRemove()
		)
	return MAGNET

def magnet(update: Update, context: CallbackContext) -> int:
	"""
	Respuesta a recibir el magnet URL del torrent
	- Se recoge el mensaje del usuario como el magnet URL
	- Pide la confirmación del usuario para empezar la descarga
	"""
	global torrent_link
	reply_keyboard = [['OK', '/cancel']]
	torrent_link = update.message.text

	logger.info(' [-] Torrent: {}'.format(torrent_link))
	update.message.reply_text(
		'Genial, si me das el ok, comenzaré con la descarga',
		reply_markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
	)
	return CONFIRM

def confirm(update: Update, context: CallbackContext) -> int:
	"""
	Respuesta a la confirmacion del usuario
	- Comienza la descarga
	"""
	logger.info(' [-] Confirmacion: {}'.format(update.message.text))

	download()
	update.message.reply_text(
		'✅ Descarga en cola',
		reply_markup=ReplyKeyboardRemove()
	)
	return ConversationHandler.END


def download():
	"""
	- Establece la conexión con qBitTorrent
	- Descarga los ficheros
	"""
	qb = Client(config.TORRENT['server'])
	qb.login(config.TORRENT['user'], config.TORRENT['pass'])
	qb.download_from_link(torrent_link, savepath=save_path)
	logger.info('✅ - {} en cola'.format(torrent_link))


def cancel(update: Update, context: CallbackContext) -> int:
	"""
	En caso de cancelación
	"""
	logger.info('❌ - El usuario ha cancelado la acción'.format(torrent_link))
	update.message.reply_text(
        '❌ Recogiendo cable...', reply_markup=ReplyKeyboardRemove()
    )
	return ConversationHandler.END

def unknown(update, context) -> None:
	"""
	En caso de obtener respuestas no pedidas ni contempladas
	"""
	update.message.reply_text(
        '❌ No te he comprendido...'
    )
	return ConversationHandler.END

### MAIN
def main() -> None:
	updater = Updater(token=config.TOKEN, use_context=True)
	dispatcher = updater.dispatcher
	down_handler = ConversationHandler(
		entry_points=[CommandHandler('start', start)],
		states = {
			TYPE: [MessageHandler(Filters.regex('^('+'|'.join([i for i in config.ALLOWED_TYPES])+')$'), type)],
			MAGNET: [MessageHandler(Filters.regex('^magnet*'), magnet)],
			CONFIRM: [MessageHandler(Filters.regex('^OK$'), confirm)],
		},
		fallbacks=[CommandHandler('cancel', cancel),MessageHandler([Filters.command], unknown)],
	)
	dispatcher.add_handler(down_handler)

	updater.start_polling()
	updater.idle()

if __name__ == '__main__':
	main()