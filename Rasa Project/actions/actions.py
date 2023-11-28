import requests
import re
import random
import json
import os.path
from neural_networks import personalized_recom
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from swiplserver import PrologMQI

DATA_PATH = 'C:/Users/Delfina/OneDrive/Escritorio/Delfina/FACULTAD/PExp/YT_ChatBot/actions/data.pl'

""" R E C O M E N D A C I O N """

class JSONDataset():

    # metodo constructor
    def __init__(self, file_path) -> None:
        self.json_path = file_path

    # insertar un nuevo dato/fila
    def add(self, element):
        data = self.load()
        data.append(element)
        with open(self.json_path, 'w') as file:
            json.dump(data, file, indent=2)

    # cargar el archivo
    def load(self): 
        if os.path.isfile(self.json_path):
            with open(self.json_path,"r") as arch:
                archivo=json.load(arch)
                arch.close()
        else:
            archivo={}
        return archivo
    
    # vaciar el archivo
    def clear(self):
        with open(self.json_path, 'w') as arch:
            arch.write("[]")
            arch.close()

last_recom = None
class ActionUpdateRecomHistory(Action):
    # actualiza el historial de búsqueda de la conversación
    def name(self) -> Text:
        return "action_update_recom_history"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        feedback = tracker.get_intent_of_latest_message()
        if (feedback == 'positive_fb'):
            op = 1
        elif (feedback == 'negative_fb'):
            op = 0
        else:
            return []

        global last_recom
        if last_recom:
            # obtengo el historial actual
            actual_history = tracker.get_slot("recom_history") or []
            nueva_recom = (str(last_recom),op)
            last_recom = None

            # agrego la nueva recomendación a la lista
            actual_history.append(nueva_recom)

            # actualizo el slot de lista
            return [SlotSet("recom_history",actual_history)]
        return []

class ActionRecommendVideo(Action):
    # accion que recomienda un video al usuario
    
    def name(self):
        return "action_recommend_video"

    # devuelve un video (no visto por el usuario) al azar
    def random_recom(self,username):

        with PrologMQI(port=8000) as mqi:
            with mqi.create_thread() as prolog_thread:
                prolog_thread.query(f"consult('{DATA_PATH}')")
                
                prolog_thread.query_async(f"cant_videos(C).")
                cant_videos = prolog_thread.query_async_result()[0]['C']    # cantidad total de videos

                prolog_thread.query_async(f"all_videos(L).")
                resultados = prolog_thread.query_async_result()             # lista de todos los videos

                # extraer los ID y filtrar los videos vistos por el usuario (si es conocido)
                candidatos = []
                i = 0
                while i<cant_videos:
                    video_id = resultados[0]['L'][i]['args'][0]
                    if username:
                        prolog_thread.query_async(f"ha_visto('{video_id}',{username}).")
                        visto = prolog_thread.query_async_result()
                        if not visto:
                            candidatos.append(f'{video_id}')
                    i=i+1

                random_index = random.randint(0, len(candidatos)-1)        # index de video al azar
                recom = list(candidatos)[random_index]
        return recom

    # carga a 'data' los videos vistos por el usuario según el archivo Prolog
    def cargar_dataset_pl(self,data,username):
        with PrologMQI(port=8000) as mqi:
            with mqi.create_thread() as prolog_thread:
                # consulta por los videos vistos del usuario
                prolog_thread.query(f"consult({DATA_PATH})")
                prolog_thread.query_async(f"videos_vistos_por_usuario({username},H).")
                historial = prolog_thread.query_async_result()[0]['H']
                # itera sobre los videos vistos
                i = 0
                while i<len(historial):
                    dato = historial[i]
                    # obtengo la informacion del video
                    video_id = dato['args'][0]
                    prolog_thread.query_async(f"get_video('{video_id}',V).")
                    video_info = prolog_thread.query_async_result()[0]['V'][0]['args']
                    opinion = dato['args'][1]
                    categoria = video_info[0]
                    duracion = video_info[1]['args'][0]
                    idioma = video_info[1]['args'][1]
                    # agrega el video al dataset
                    data.add({"VideoID": f"{video_id}","Categoria": f"{categoria}","Duracion": f"{duracion}","Idioma": f"{idioma}","Opinion": f"{opinion}"})
                    i=i+1
    
    # carga a 'data' los videos vistos por el usuario en la sesión actual (historial de recomendaciones)
    def cargar_dataset_sesion(data):
        # a implementar: analogo a cargar_dataset_pl pero desde recom_history como fuente
        historial = Tracker.get_slot("recom_history")
        i = 0
        if historial:
            with PrologMQI(port=8000) as mqi:
                with mqi.create_thread() as prolog_thread:
                    prolog_thread.query(f"consult({DATA_PATH})")
                    while i<len(historial):
                        dato = historial[i]
                        # obtengo la informacion del video
                        print(dato)
                        video_id = dato['args'][0]
                        prolog_thread.query_async(f"get_video('{video_id}',V).")
                        video_info = prolog_thread.query_async_result()[0]['V'][0]['args']
                        opinion = dato['args'][1]
                        categoria = video_info[0]
                        duracion = video_info[1]['args'][0]
                        idioma = video_info[1]['args'][1]
                        # agrega el video al dataset
                        data.add({"VideoID": f"{video_id}","Categoria": f"{categoria}","Duracion": f"{duracion}","Idioma": f"{idioma}","Opinion": f"{opinion}"})
                        i=i+1
            return []

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        MIN_HISTORY = 10        # cantidad mínima de videos vistos por el usuario para poder recomendar con redes neuronales
        cant_vistos_sesion = 0  # cantidad de videos vistos segun sesion actual
        cant_vistos_pl = 0      # cantidad segun historial de videos vistos en archivo Prolog

        username = tracker.get_slot("username")

        # determino si el usuario es conocido - es decir - si existe en el archivo Prolog
        if username:
            with PrologMQI(port=8000) as mqi:
                with mqi.create_thread() as prolog_thread:
                    prolog_thread.query(f"consult({DATA_PATH})")
                    prolog_thread.query_async(f"usuario({username}).")
                    conocido = prolog_thread.query_async_result()
                    if conocido:
                        prolog_thread.query_async(f"videos_vistos_por_usuario({username},H).")
                        cant_vistos_pl = len(prolog_thread.query_async_result()[0]['H'])

        # cantidad de videos vistos por el usuario
        ACTUAL_HISTORY = cant_vistos_sesion + cant_vistos_pl  
        print('El usuario ha visto [',ACTUAL_HISTORY,'] videos.')

        # si no se tiene registro suficiente del usuario: se recomienda un video al azar
        if ACTUAL_HISTORY <= MIN_HISTORY:
            print('Registro insuficiente: la recomendación es al azar')
            recom = self.random_recom({username})
        # si se tiene registro suficiente: se ejecuta el algoritmo de redes neuronales
        else:

            print('Registro suficiente: la recomendacion es personalizada')
            # creo el dataset
            data = JSONDataset("ChatBot_new\\actions\\viewed_videos.json")
            
            # cargo el dataset
            if conocido:
                self.cargar_dataset_pl(data,username)
            # agrego los datos del historial de recomendaciones
            self.cargar_dataset_sesion(data)

            # con el dataset cargado ejecuto neural_networks para todos los videos no vistos por el usuario
            recom = personalized_recom(data)
            
            # vaciar viewed_videos
            data.clear()

        dispatcher.utter_message(f"Por supuesto! Tal vez esto te guste... https://www.youtube.com/watch?v={recom}")

        # actualizo last recommended
        global last_recom
        last_recom = recom


""" B U S Q U E D A """

nueva_busqueda = None
class ActionUpdateSearchHistory(Action):
    # actualiza el historial de búsqueda de la conversación
    def name(self) -> Text:
        return "action_update_search_history"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        global nueva_busqueda
        if nueva_busqueda != None:

            # obtengo el historial actual
            actual_history = tracker.get_slot("search_history") or []

            # agrego la nueva búsqueda a la lista
            actual_history.append(nueva_busqueda)

            nueva_busqueda = None

            dispatcher.utter_message(text='Y bien... ¿Qué te ha parecido el video?')

            # actualizo el slot de lista
            return [SlotSet("search_history",actual_history)]  

class ActionSetSlotLastSK(Action):
    def name(self) -> Text:
        return "action_set_lsk"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if nueva_busqueda:
            return[SlotSet("last_search_key",nueva_busqueda[1])]
        return[]

class ActionSearchVideo(Action):
    # accion de búsqueda de videos en YouTube
    
    def name(self):
        return "action_search_video"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        if (str(tracker.get_intent_of_latest_message()) == 'ask_for_search'):
            # extracción de la clave de búsqueda: texto entre comillas dobles
            entre_comillas = re.findall(r'"([^"]*)"', tracker.latest_message['text'])
            if entre_comillas:
                search_key_url = entre_comillas[0]
            else:
                return[SlotSet("last_search_key",None)]
        elif (str(tracker.get_intent_of_latest_message()) == 'repeat_search'):
            # extracción de la clave de búsqueda: la misma que la de la búsqueda anterior
            search_key_url = tracker.get_slot("last_search_key")
            if not search_key_url:
                dispatcher.utter_message('Mmm, la verdad es que no tengo registro de una búsqueda anterior.')
        else:
            return []
        
        if search_key_url:
            
            api_key = 'AIzaSyBOMEHk9dlGu6PQntgjBtydprgQO9JADJ8'     # clave de API - YouTube
            max_resultados=10                                       # cantidad maxima de resultados deseados
            # generación del URL de la búsqueda de YouTube
            youtube_api_url = f'https://www.googleapis.com/youtube/v3/search?q={search_key_url}&key={api_key}&maxResults={max_resultados}&type=video'

            # búsqueda mediante solicitud a la API de YouTube
            response = requests.get(youtube_api_url)
            video_data = response.json()
            n = len(video_data)     # cantidad de resultados hallados - n <= max_resultados

            # si la búsqueda arroja resultados
            if 'items' in video_data:
                print('Realizando búsqueda - search key: ',search_key_url,'\n')
                # arroja un link al azar de los n resultados hallados
                random_result = random.randint(0, n-1)
                video_id = video_data['items'][random_result]['id']['videoId']
                dispatcher.utter_message(text=f'Claro! Aquí te va el resultado de la búsqueda "{search_key_url}" en YouTube: ' 
                                        + f'https://www.youtube.com/watch?v={video_id}')
                # actualizacion del historial
                global nueva_busqueda 
                nueva_busqueda = (str(search_key_url), str(video_id))
                # manejo de contexto: se "recuerda" lo último que se buscó
                return[SlotSet("last_search_key",search_key_url)]
            else:
                dispatcher.utter_message(text=f'Lo siento, no se encontraron resultados en YouTube para la búsqueda "{search_key_url}".')
        else:
            return[SlotSet("last_search_key",None)]

class ActionDisplayHistory(Action):
    # actualiza el historial de búsqueda de la conversación
    def name(self) -> Text:
        return "action_display_history"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # HISTORIAL DE BUSQUEDAS
        actual_history = tracker.get_slot("search_history") or []
        cant_elementos = len(actual_history)
        historial = "H I S T O R I A L   D E   B U S Q U E D A S:" + ' [' +  str(cant_elementos) + ' elemento/s] \n' 
        # agrega las búsquedas de menos a mas recientes
        i = 0
        for element in actual_history:
            e = str(i) + '. SK: ' + str(element[0]) + ', Resultado: https://www.youtube.com/watch?v=' + str(element[1]) + '\n'
            historial = historial + str(e)
            i = i+1
        dispatcher.utter_message(historial)