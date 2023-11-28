import requests
import re
import random
import json
import os.path
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from swiplserver import PrologMQI

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
    # funciona

    # cargar el archivo
    def load(self): 
        if os.path.isfile(self.json_path):
            with open(self.json_path,"r") as arch:
                archivo=json.load(arch)
                arch.close()
        else:
            archivo={}
        return archivo
    # funciona
    
    # vaciar el archivo
    def clear(self):
        with open(self.json_path, 'w') as arch:
            arch.write("[]")
            arch.close()
    # funciona

MIN_HISTORY = 10    # cantidad mínima de videos vistos por el usuario para poder recomendar con redes neuronales

username = 'Delfina'
print(username)

cant_vistos_sesion = 0  # cantidad de videos vistos segun sesion actual
cant_vistos_pl = 0      # cantidad segun historial de videos vistos en prolog

DATA_PATH = 'C:/Users/Delfina/OneDrive/Escritorio/Delfina/FACULTAD/PExp/YT_ChatBot/actions/data.pl'
# determino si el usuario es conocido - es decir - si existe en el archivo Prolog
if username:
    with PrologMQI(port=8000) as mqi:
        with mqi.create_thread() as prolog_thread:
            prolog_thread.query(f"consult('{DATA_PATH}')")
            prolog_thread.query_async(f"usuario('Delfina').")
            conocido = prolog_thread.query_async_result()
            if conocido:
                prolog_thread.query_async(f"videos_vistos_por_usuario({username},H).")
                cant_vistos_pl = len(prolog_thread.query_async_result()[0]['H'])

ACTUAL_HISTORY = cant_vistos_sesion + cant_vistos_pl  # cantidad de videos vistos por el usuario
print(ACTUAL_HISTORY)

data = JSONDataset("C:\\Users\\Delfina\\OneDrive\\Escritorio\\Delfina\\FACULTAD\\PExp\\YT_ChatBot\\actions\\viewed_videos.json")
username = 'Delfina'
with PrologMQI(port=8000) as mqi:
    with mqi.create_thread() as prolog_thread:

        # consulta por los videos vistos del usuario
        prolog_thread.query(f"consult('{DATA_PATH}')")
        prolog_thread.query_async(f"videos_vistos_por_usuario({username},H).")
        historial = prolog_thread.query_async_result()[0]['H']

        # itera sobre los videos vistos y los carga al dataset
        i = 0
        while i<len(historial):
            
            dato = historial[i]

            # obtengo la informacion del video
            video_id = dato['args'][0]
            opinion = dato['args'][1]
            prolog_thread.query_async(f"get_video('{video_id}',V).")
            video_info = prolog_thread.query_async_result()[0]['V'][0]['args']
            categoria = video_info[0]
            duracion = video_info[1]['args'][0]
            idioma = video_info[1]['args'][1]
            print(idioma)

            row = {"VideoID": f"{video_id}","Categoria": f"{categoria}","Duracion": f"{duracion}","Idioma": f"{idioma}","Opinion": f"{opinion}"}
            data.add(row)
            i=i+1
            


"""
"""