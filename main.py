import config, logging
from qbittorrent import Client
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, Bot
from telegram.ext import Updater, CommandHandler
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.ext.conversationhandler import ConversationHandler

### Config inicial
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TDWB')
torrent_link, save_path = '',''
TYPE, MAGNET, CONFIRM = range(3)

### Funciones del bot
def start(update: Update, context: CallbackContext) -> None:
	"""
	Dar una descripción del bot y sus funciones actuales
	"""
	reply_keyboard = [['/download'], ['/status', '/clear']]
	logger.info(' El usuario ha ejecutado /start')
	update.message.reply_text(
        'Escoge una opción:',
		reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )

def help(update, context) -> None:
	"""
	Muestra una ayuda con los comandos disponibles
	"""
	logger.info(' El usuario ha ejecutado /help')
	update.message.reply_text(
		'Soy TorrentDownloaderBot, un Bot de descargas de torrents creado por BenoBelmont\n\n'
        'Yo solo sirvo a mi creador, pero puedes acceder a mi código fuente '
        'sin problema alguno en https://github.com/jorgegomzar/TorrentDownloaderBot\n\n'
        'Actualmente, entre mis funciones, se incluyen:\n'
        '- /start - Iniciar la conversación\n'
		'- /download - Descargar un torrent\n'
		'- /status - Mostrar la cola de descargas actuales\n'
		'- /clear - Limpiar la cola de descargas\n'
		'- /help - Mostrar este mensaje'
    )

def download(update: Update, context: CallbackContext) -> int:
	"""
	Respuesta al comando "/start"
	- Comprueba la ID para saber si es un usuario permitido
		- Si lo es, pregunta por el tipo de media
		- Si no lo es, finaliza la conversación y exporta en logs info adicional
	"""
	global torrent_link, save_path
	torrent_link, save_path = '',''
	reply_keyboard = [config.ALLOWED_TYPES]

	if int(update.effective_chat.id) not in config.ALLOWED_IDS:
		not_allowed(update)
		return ConversationHandler.END
	else:
		logger.info('ℹ - Un usuario CON permiso solicita usar el bot')
		update.message.reply_text(
			'Hola, ¿qué tipo de media vamos a descargar?\n'
			'Responde /cancel en cualquier momento para cancelar el proceso',
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

	download_torrent()
	update.message.reply_text(
		'✅ Descarga en cola',
		reply_markup=ReplyKeyboardRemove()
	)
	return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
	"""
	En caso de cancelación
	"""
	logger.info('❌ - El usuario ha cancelado la acción'.format(torrent_link))
	update.message.reply_text(
        '❌ Recogiendo cable...', reply_markup=ReplyKeyboardRemove()
    )
	return ConversationHandler.END

def status(update: Update, context: CallbackContext) -> None:
	"""
	Muestra el estado de la cola de descargas
	"""
	if int(update.effective_chat.id) not in config.ALLOWED_IDS:
		not_allowed(update)
	else:
		logger.info(' El usuario ha ejecutado /status')
		qb = Client(config.TORRENT['server'])
		qb.login(config.TORRENT['user'], config.TORRENT['pass'])
		torrents = qb.torrents()
		qb.logout()
		if len(torrents) == 0:
			update.message.reply_text('Parece que en este momento no hay nada en cola')
		else:
			update.message.reply_text('Hay {} torrents en cola\n'.format(len(torrents)))
			for torrent in torrents:
				update.message.reply_text(
					'Torrent: {}\nEstado: {}\nTamaño: {}\nProgreso: {}%\nTasa de descarga: {}/s\n'.format(
						torrent['name'],
						torrent['state'],
						get_size_format(torrent['total_size']),
						str(float(torrent['progress'])*100),
						get_size_format(torrent['dlspeed']),
						)
					)

def clear(update: Update, context: CallbackContext) -> None:
	"""
	Limpia los torrents finalizados de la cola de descarga
	"""
	FINISHED_STATES = [
		'uploading',
		'pausedUP',
		'stalledUP',
		'queuedUP',
	]
	if int(update.effective_chat.id) not in config.ALLOWED_IDS:
		not_allowed(update)
	else:
		logger.info(' Un usuario CON permiso ha ejecutado /clear')
		qb = Client(config.TORRENT['server'])
		qb.login(config.TORRENT['user'], config.TORRENT['pass'])
		torrents = qb.torrents()
		del_torrents = len(torrents)
		for torrent in torrents:
			if torrent['state'] in FINISHED_STATES:
				qb.delete(torrent['hash'])
		torrents = qb.torrents()
		del_torrents = del_torrents - len(torrents)
		qb.logout()
		logger.info('{} torrents han sido eliminados de la cola'.format(del_torrents))
		if del_torrents != 0:
			update.message.reply_text('Borrados todos los torrents finalizados')
		else:
			update.message.reply_text('No se ha eliminado ningún torrent de la cola')

def unknown(update: Update, context: CallbackContext) -> None:
	"""
	El usuario ha introducido un comando desconocido
	"""
	logger.info(' El usuario ha ejecutado {}'.format(update.message.text))
	update.message.reply_text('No te he entendido bien, por favor, usa las opciones disponibles.')

# Auxiliares
def get_size_format(b, factor=1024, suffix="B"):
    """
    Scale bytes to its proper byte format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
		Source: https://www.thepythoncode.com/article/download-torrent-files-in-python
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"

def not_allowed(update):
	logger.info('⚠️- Un usuario SIN permiso ha intentado usar el bot')
	logger.info('Chat ID: ' + str(update.effective_chat.id))
	logger.info('Usuario: ' + str(update.effective_chat.first_name) + ' ' + str(update.effective_chat.last_name))
	logger.info('Bio: ' + str(update.effective_chat.bio))
	update.message.reply_text('❌ No tienes permiso para hacer eso')

def download_torrent():
	"""
	- Establece la conexión con qBitTorrent
	- Descarga los ficheros
	"""
	qb = Client(config.TORRENT['server'])
	qb.login(config.TORRENT['user'], config.TORRENT['pass'])
	qb.download_from_link(torrent_link, savepath=save_path)
	qb.logout()
	logger.info('✅ - {} en cola'.format(torrent_link))


### MAIN ###
def main() -> None:
	updater = Updater(token=config.TOKEN, use_context=True)
	dispatcher = updater.dispatcher
	down_handler = ConversationHandler(
		entry_points=[CommandHandler('download', download)],
		states = {
			TYPE: [MessageHandler(Filters.regex('^('+'|'.join([i for i in config.ALLOWED_TYPES])+')$'), type)],
			MAGNET: [MessageHandler(Filters.regex('^magnet*'), magnet)],
			CONFIRM: [MessageHandler(Filters.regex('^OK$'), confirm)],
		},
		fallbacks=[CommandHandler('cancel', cancel),],
	)
	dispatcher.add_handler(down_handler)
	dispatcher.add_handler(CommandHandler('start', start))
	dispatcher.add_handler(CommandHandler('status', status))
	dispatcher.add_handler(CommandHandler('clear', clear))
	dispatcher.add_handler(CommandHandler('help', help))
	dispatcher.add_handler(MessageHandler(Filters.command, unknown))

	updater.start_polling()
	updater.idle()

if __name__ == '__main__':
	main()