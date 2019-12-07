# -*- coding: utf-8 -*-

import os
import sys
import logging
import signal

from flask import Flask, request
from flask_cors import CORS
from logging.handlers import RotatingFileHandler
from cheroot.wsgi import Server as WSGIServer
from cheroot.ssl.builtin import BuiltinSSLAdapter

from Classes.Utils import Utils
from Classes.Parser import Parser
from Classes.RequestFormater import RequestFormatter
from Classes.Cache_control import CacheControl
from Classes.JsonWorker import JsonFormater
from Classes.Database import Database

app_version = '1.0.1'

execute = None
token = None
server = None
database = None

cache_control = CacheControl()
json_result = JsonFormater.json_result

app = Flask(__name__)
CORS(app)

@app.route('/api/v1/unidadeExploracao/<int:id>', methods=['GET'])
def get_unidadeExploracao(id):
    global database
    log_main.info('--> /api/v1/unidadeExploracao/{} [GET]'.format(id))
    try:
        tkn = request.headers['token_auth']
        if token == tkn:
            try:
                result = database.query_exec('SELECT * FROM UnidadeExploracao WHERE idUnidadeExploracao = {};'.format(id))
                if result['State']:
                    if result['Result']:
                        return json_result(200, {'state': 'Sucess', 'message': result['Result']})
                    else:
                        return json_result(200, {'state': 'Sucess', 'message': 'Id Consultado não existe!'})
                else:
                    log_main.exception('--> /api/v1/unidadeExploracao/{} [GET]: [{}]'.format(id, result['Result']))
                    return json_result(500, {'state': 'error', 'message': 'Erro Desconhecido'})
            except Exception as e:
                log_main.exception('--> /api/v1/unidadeExploracao/{} [GET]: [{}]'.format(id, e))
                return json_result(500, {'state': 'error', 'message': 'Erro Desconhecido'})
        return json_result(401, {'state': 'unauthorized', 'message': 'Token Invalido'})
    except:
        return json_result(401, {'state': 'unauthorized', 'message': 'Token Não Informado'})


def initiate():
    log_main.info('Iniciando a API versão: {}'.format(app_version))

    signal.signal(signal.SIGTERM, finalize)
    signal.signal(signal.SIGINT, finalize)

    global token, database

    token = conf.get('Auth', 'Token', fallback='14acd1c3b2f50c1e7354668f7d0b4057')

    log_main.warning('Iniciando conexão com banco de dados ...')
    try:
        db = os.path.join(workdir, conf.get('Database', 'Database', fallback='data.db'))
        database = Database(db)
    except Exception as e:
        log_main.exception('Erro ao iniciar a conexão com o banco de dados: [{}]'.format(e))

    _port = conf.getint('Flask', 'Port', fallback=8860)
    _host = conf.get('Flask', 'Host', fallback='0.0.0.0')
    _threads = conf.getint('Flask', 'Threads', fallback=100)
    _ssl_cert = os.path.join(workdir, 'SSL', conf.get('Flask', 'SSL_Cert', fallback=''))
    _ssl_key = os.path.join(workdir, 'SSL', conf.get('Flask', 'SSL_Key', fallback=''))
    try:
        _ssl_enabled = os.path.isfile(_ssl_cert) and os.path.isfile(_ssl_key)
    except Exception:
        _ssl_enabled = False

    if len(sys.argv) > 1:
        if sys.argv[1] in ('-v', '--version'):
            print('API')
            print('Versão: {}'.format(app_version))
            sys.exit(0)
        elif sys.argv[1] in ('-d', '--debug'):
            app.run(host=_host, port=_port, threaded=True, debug=True)
        else:
            print('ERRO | Parâmetro desconhecido: {}'.format(sys.argv))
            sys.exit(2)
    else:
        global server
        server = WSGIServer(bind_addr=(_host, _port), wsgi_app=app, numthreads=_threads)
        if _ssl_enabled:
            server.ssl_adapter = BuiltinSSLAdapter(_ssl_cert, _ssl_key)
        server.start()


def finalize(signum, desc):
    global execute, server, database
    log_main.info('Recebi o sinal [{}] Desc [{}], finalizando...'.format(signum, desc))

    log_main.warning('Limpando Cache Control ...')
    cache_control.clear()

    log_main.warning('Encerrando conexão com banco de dados ...')
    database.db_close()

    if server is not None:
        log_main.warning('Parando Serviço ...')
        server.stop()
    if execute:
        execute = False
    else:
        sys.exit(2)


if __name__ == '__main__':
    execute = True
    workdir = Utils.get_workdir()
    conf = Parser(os.path.join(workdir, 'config.ini')).conf_get()
    _level = conf.getint('Debug', 'Level', fallback=3)
    debug_dir = os.path.join(workdir, 'debug')
    log_file_path = os.path.join(debug_dir, 'API.log')
    if not os.path.exists(debug_dir):
        os.mkdir(debug_dir, 0o775)
    log_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024 * 10, backupCount=10)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(RequestFormatter(
        '[%(asctime)s] | %(levelname)s | %(name)s | %(remote_addr)s | %(method)s | %(url)s | %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(log_handler)
    log_main = logging.getLogger('API:' + str(os.getpid()))
    app.logger.addHandler(log_handler)
    app.debug = True

    initiate()