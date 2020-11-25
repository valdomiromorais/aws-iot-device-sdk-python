"""
/*
 * Copyright 2010-2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *  http://aws.amazon.com/apache2.0
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */
 """
# A version with comments in pt_BR for Brazilian users for Valdomiro Morais (https://github.com/valdomiromorais)

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging  # usado para registro de logs
import time  # usado usar a função sleep
import argparse  # trata os argumentos de linha de comando
import json  # converte dicionários em jason

# As ações permitidas: publish (publicar tópicos),
# subscribe (assinar tópicos) ou both (ambos)
AllowedActions = ['both', 'publish', 'subscribe']

# Ler os parâmetros na linha de comando
# Argumentos para o método add_argument (https://docs.python.org/3/library/argparse.html):
#  1. action: especifica como o argumento em questão deve ser tratado:
#   a. "store": armazena o valor argumento
#   b. "store_const": Este armazena o valor especificado pela pela palavra-chave argumento "const":
#       Ex.: parser.add_argument('--foo', action='store_const', const=42)
#   c. "store_true" ou "store_false":  Estes são casos especiais de "store_const" usados para armazenar
#      os valores True e False respectivamente.
#  2. required: em geral, o módulo argparse assume que flags como -f e --bar indicam argumentos opcionais,
#     que podem sempre ser omitidos na linha de comando (CL). Para torna uma opção requerida/obrigatória,
#     True pode ser especificado para o argumento palavra-chave "required="
#  3. dest: A maioria das ações de ArgumentParser adicionam algum valor como atributo do objeto retornado
#     pela parse_args(). O nome deste atributo é determinado pelo argumento palavra-chave "dest" de add_argument().
#  4. help: O valor de "help" é uma string contendo uma breve descrição do argumento. Qdo um usuário requer "help"
#     (normalmente usando -h ou --help na linha de comando), esta descrição de ajuda irá ser mostrada com cada argumento:
#  5. default: Valor padrão caso o argumento não seja passado
parser = argparse.ArgumentParser()
parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
parser.add_argument("-p", "--port", action="store", dest="port", type=int, help="Port number override")
parser.add_argument("-w", "--websocket", action="store_true", dest="useWebsocket", default=False,
                    help="Use MQTT over WebSocket")
parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicPubSub",
                    help="Targeted client id")
parser.add_argument("-t", "--topic", action="store", dest="topic", default="sdk/test/Python", help="Targeted topic")
parser.add_argument("-m", "--mode", action="store", dest="mode", default="both",
                    help="Operation modes: %s" % str(AllowedActions))
parser.add_argument("-M", "--message", action="store", dest="message", default="Hello World!",
                    help="Message to publish")  # Será usada para enviar mensagem como publisher no loop infinito

# Aqui os argumento da linha de comando são transferidos para a variável 'args'
args = parser.parse_args()
host = args.host  # ENDPOINT da conta AWS no serviço AWS IoT
rootCAPath = args.rootCAPath  # o path (caminho) do arquivo que contém a Root CA (Root Certificate Authority): https://en.wikipedia.org/wiki/Root_certificate
certificatePath = args.certificatePath  # o path (caminho) para o arquivo que contém o certificado de 'thing' (coisa)
privateKeyPath = args.privateKeyPath  # o path (caminho) para o arquivo que contém a chave privada da 'thing' (coisa)
port = args.port  # número do/a porto/a de acesso
useWebsocket = args.useWebsocket  # verifica se vai usar webSockets ou não
clientId = args.clientId  # Id (identificador) do cliente. Se não for informado o padrão será "basicPubSub"
topic = args.topic  # Tópico de mensagen MQTT pretendido publicar e/ou assinar

# Se o modo informado não for 'publish' ou 'subscribe' ou 'both' é um erro
# O modo foi definido para decidir se o programa deve se comportar como um
# 'publisher', um 'subscriber' ou ambos
if args.mode not in AllowedActions:
    parser.error("Unknown --mode option %s. Must be one of %s" % (args.mode, str(AllowedActions)))
    exit(2)
# não pode usar webSockets e certificado X.509 ao mesmo tempo.
if args.useWebsocket and args.certificatePath and args.privateKeyPath:
    parser.error("X.509 cert authentication and WebSocket are mutual exclusive. Please pick one.")
    exit(2)
# Se escolheu não usar webSockets então certificatePath e privateKeyPath são obrigatórios
if not args.useWebsocket and (not args.certificatePath or not args.privateKeyPath):
    parser.error("Missing credentials for authentication.")
    exit(2)

# Portas padrão
if args.useWebsocket and not args.port:  # Qdo nenhuma porta for informada para WebSocket qdo escolhido,..
    port = 443  # ... a padrão será 443
if not args.useWebsocket and not args.port:  # Qdo nenhuma porta for informada para não-WebSocket,...
    port = 8883  # ... a padrão será 8883

# Configurando o sistema de logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


# Qdo o cliente foi permitido assinar tópico
# deve ter uma função de callback para tratar
# as mensagens MQTT vindas do Broker
# a mensagem (msg) contém o tópico (msg.topic) e
# a "carga útil" (msg.payload): normalmente o json
# enviado pelo publisher
def customCallback(client, userdata, msg):
    print("Received a new message: ")
    print(msg.payload)
    print("from topic: ")
    print(msg.topic)
    print("--------------\n\n")


# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
if useWebsocket:  # se o usuário decidiu usar webSockets
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId, useWebsocket=True)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath)
else:  # se o usuário decidiu não usar webSockets
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# Configurações da conexão do AWSIoTMQTTClient
# (Ver https://pypi.org/project/AWSIoTPythonSDK/1.0.0/ (só a descrição do projeto. A versão atual é 1.4+))
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

# Conecta ao Broker
myAWSIoTMQTTClient.connect()

# Se decidiu ser um topic subscriber (assinante de um tópico)
# ou ambos (subscriber e publusher ao mesmo tempo)...
if args.mode == 'both' or args.mode == 'subscribe':
    # ... assina o tópico definido na linha de comando e define
    # a funça de callback (usada para agir diante da mensagem enviada pelo publisher)
    myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)

# Aguarda 2 segundos
time.sleep(2)

# Public em um mesmo tópico em um loop infinito
loopCount = 0  # conta quanto loops foram dados. Vai ser usado para diferenciar entre as mensagem
while True:
    # Se decidiu ser um topic publisher (publicador de um tópico)
    # ou ambos (subscriber e publusher ao mesmo tempo)...
    if args.mode == 'both' or args.mode == 'publish':
        # Prepara a mensagem a ser publicada (deve ser alterada pela necessidade)
        message = {'message': args.message, 'sequence': loopCount}
        messageJson = json.dumps(message)

        # Publica a mensagem no tópico escolhido com QoS 1 (Pelo menos uma vez)
        # Para mais informações sobre Qos ver https://www.hivemq.com/blog/mqtt-essentials-part-6-mqtt-quality-of-service-levels/
        myAWSIoTMQTTClient.publish(topic, messageJson, 1)

        # Se este cliente for um publisher, dá saída do tópico publicado
        # co a mensagem respectiva
        if args.mode == 'publish':
            print('Published topic %s: %s\n' % (topic, messageJson))

        loopCount += 1
    time.sleep(1)  # 1 segundo entre as mensagens

# Uso típico:
#   $ python basicPubSub.py
#   --endpoint "<coloque o seu>-ats.iot.<regia-aws-da-coisa>.amazonaws.com"
#   --rootCA "<caminho para o arquivo da root CA>"
#   --cert "<caminho para o arquivo do certificado digital>"
#   --key "<caminho para o arquivo da chave privada>"
#   --clientId "seuClientID"
#   --topic "meu/topico"
#   --mode "" (o padrão é 'both')
#   --message "" (o padrão é 'Hello word!')
