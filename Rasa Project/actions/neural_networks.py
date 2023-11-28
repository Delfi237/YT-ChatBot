import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from swiplserver import PrologMQI

# algoritmo de recomendacion personalizada - retorna id_video
def personalized_recom(username):

  DATA_PATH = 'C:/Users/Delfina/OneDrive/Escritorio/Delfina/FACULTAD/PExp/YT_ChatBot/actions/data.pl'

  # codificación previa: se hace antes de crear el dataset a partir de los datos en Prolog 
  # esto es para evitar errores de tipo 'unknown label' en LabelEncoder 
  label_encoder_cat = LabelEncoder()
  label_encoder_dur = LabelEncoder()
  label_encoder_lang = LabelEncoder()
  with PrologMQI(port=8000) as mqi:
    with mqi.create_thread() as prolog_thread:
      prolog_thread.query(f"consult('{DATA_PATH}')")
      # obtengo lista de categorias para encodear
      prolog_thread.query_async(f"all_categorias(V)")
      categorias = prolog_thread.query_async_result()[0]['V']
      prolog_thread.query_async(f"all_duraciones(V)")
      duraciones = prolog_thread.query_async_result()[0]['V']
      prolog_thread.query_async(f"all_idiomas(V)")
      idiomas = prolog_thread.query_async_result()[0]['V']

      label_encoder_cat.fit(np.array(categorias))
      label_encoder_dur.fit(np.array(duraciones))
      label_encoder_lang.fit(np.array(idiomas))

  # creacion del dataset
  df = pd.read_json('viewed_videos.json')
  print(df)

  # codificacion de los atributos discretos del dataset
  df['Categoria']=label_encoder_cat.transform(df['Categoria'])
  df['Duracion']=label_encoder_dur.transform(df['Duracion'])
  df['Idioma']=label_encoder_lang.transform(df['Idioma'])

  # definicion de los datos de entrenamiento
  x = df[['Categoria','Duracion','Idioma']].values
  y = df['Opinion'].values
  x_train, x_test, y_train, y_test = train_test_split(x,y,test_size=0.2,random_state=42)

  # creacion del modelo
  model = keras.Sequential([
      keras.layers.Input(shape=(x.shape[1],)),
      keras.layers.Dense(64, activation='relu'),
      keras.layers.Dense(32, activation='relu'),
      keras.layers.Dense(1, activation='sigmoid')
  ])

  # entrenamiento del modelo
  model.compile(loss='binary_crossentropy',optimizer='adam',metrics=['accuracy'])
  model.fit(x_train,y_train,epochs=10,batch_size=64,validation_data=(x_test,y_test))
  loss, accuracy = model.evaluate(x_test,y_test)
  print(f'Loss: {loss}, Accuracy: {accuracy}')

  # definición de los videos candidatos: tuplas de prueba para el algoritmo
  # los candidatos a recomendación son los videos no vistos del ususario
  if username:
    with PrologMQI(port=8000) as mqi:
      with mqi.create_thread() as prolog_thread:
          prolog_thread.query(f"consult('{DATA_PATH}')")
          prolog_thread.query_async(f"videos_no_vistos_por_usuario('{username}',V)")
          candidatos = prolog_thread.query_async_result()[0]['V']
  
  # itera sobre los candidatos para hallar una recomendacion
  i=0
  while i<len(candidatos):

    # extracción de los datos del video i
    recom = candidatos[i]['args'][0]
    cat = candidatos[i]['args'][1]['args'][0]
    dur = candidatos[i]['args'][1]['args'][1]['args'][0]
    idioma = candidatos[i]['args'][1]['args'][1]['args'][1]
    # codificacion de los atributos discretos
    sample_video = np.array([[label_encoder_cat.transform([f'{cat}']),
                              label_encoder_dur.transform([f'{dur}']),
                              label_encoder_lang.transform([f'{idioma}'])]])
    
    # utiliza el modelo para predecir si el video puede gustar o no
    prediction = model.predict(sample_video)
    if prediction >= 0.5:
      print(f'Recomendación hallada! https://www.youtube.com/watch?v={recom}')
      return recom
    i=i+1

  return None

# El usuario de ejemplo ha visto:
#  - 3 videos de 'Animacion'               [ buena reseña: 3 | mala reseña: 0 ]
#  - 2 videos de 'Misterio y Terror'       [ 1 | 1 ]
#  - 1 video de 'Historia y Politica'      [ 0 | 1 ]
#  - 2 videos de 'Ciencia y Tecnologia'    [ 2 | 1 ]
#  - 2 videos de 'Videojuegos'             [ 1 | 1 ]
# recomendacion = personalized_recom('Delfina')