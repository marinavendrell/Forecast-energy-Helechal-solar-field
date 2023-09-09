

## Importar librerías

import numpy as np
import pandas as pd
import pickle
import requests
import calendar

from datetime import datetime, timedelta
from janitor import clean_names

import pytz

import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.utf8')
#locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
locale.setlocale(locale.LC_ALL, 'C')

from sklearn.preprocessing import OneHotEncoder
from category_encoders import TargetEncoder

from sklearn.feature_selection import mutual_info_regression

from sklearn.model_selection import TimeSeriesSplit

from sklearn.pipeline import Pipeline

from xgboost import XGBRegressor

from sklearn.model_selection import RandomizedSearchCV

from sklearn.metrics import mean_absolute_error
from sklearn.metrics import r2_score
from sklearn.metrics import mean_squared_error


import warnings
warnings.filterwarnings("ignore")

import streamlit as st

### Authentication
# Accede a la API key desde los secretos de Streamlit
api_key = st.secrets["api_key"]

# Define las cabeceras para la solicitud HTTP
headers = {"Authorization": api_key}


### Conexión Open-Meteo para 7 días vista de precipitación -> Servirá para la previsión de limpiezas
def conexion_open_meteo(fecha_hora_actual):
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude=38.6628444&longitude=-5.391886111111112&hourly=precipitation_probability,cloudcover&timezone=Europe%2FBerlin"
    
    response = requests.get(url)
    
    # Obtener los datos JSON de la respuesta
    data = response.json()
    
    # Extraer la parte 'hourly' de los datos
    hourly_data = data.get('hourly', {})
    
    # Crear un DataFrame a partir de los datos de precipitación
    df = pd.DataFrame(hourly_data)
    
    # Cambiamos a datetime
    df['date'] = pd.to_datetime(df['time']) #, format='%Y-%m-%dT%H:%M'
    
    #Indexamos por lo que nos interesa
    df = df[['date', 'precipitation_probability','cloudcover']]
    
    # Sumar 7 dias
    desplazamiento = timedelta(days=7) #Depende de la hora en que se ejecute te dará 7 días o menos (6 días)
    fecha_7_dias_despues = fecha_hora_actual + desplazamiento
    
    # Filtrar el DataFrame para incluir solo fechas mayores o iguales a la fecha y hora actual
    df = df[(df['date'] >= fecha_hora_actual + timedelta(hours=1)) & (df['date'] <= fecha_7_dias_despues)]

    # Mostrar el DataFrame
    return(df)



### Conexión OpenWeatherMap con datos a futuro
def conexion_openweathermap_futuro():

    #Zona geográfica:la nava
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat=38.6628444&lon=-5.391886111111112&exclude=current,minutely,alerts&appid={api_key}&units=metric"
    querystring = {"api_key": api_key}
    response = requests.get(url, params=querystring, verify=False)

    response.status_code == requests.codes.ok
    content = response.json()

    df = pd.json_normalize(content, record_path =['hourly'])
    objeto = [df, pd.DataFrame(df['weather'].tolist()).iloc[:, :4]]
    df = pd.concat(objeto, axis=1)
    df = pd.concat([df.drop([0,'weather'], axis=1), df[0].apply(pd.Series)], axis=1)

    ###Corrección de nombres manual
    df.rename(columns = {'id':'weather_id', 'main':'weather_main', 'description':'weather_description', 'icon':'weather_icon'}, inplace=True)

    #Indexamos por las variables de interés para poder juntarlo también con los históricos

    df = df[['dt','temp','pressure', 'humidity',
             'dew_point','feels_like','wind_speed', 'wind_deg',
            'clouds', 'weather_id', 'weather_main', 'weather_description', 'weather_icon']]

    return(df)


### Conexión OpenWeatherMap con datos a pasado
def conexion_openweathermap_pasado(fecha_hora_actual,fecha_24_horas_antes):

    #Calculamos la fecha y hora actuales y 24h previas. Esta será la hora de Madrid, España
    
    def obtener_fecha_hora_madrid():
        zona_horaria_madrid = pytz.timezone('Europe/Madrid')
        fecha_hora_madrid = datetime.now(zona_horaria_madrid)
        return fecha_hora_madrid.replace(minute=0, second=0, microsecond=0)
    

    #fecha_hora_actual = datetime(2022, 10, 5, 0)
    fecha_hora_actual =obtener_fecha_hora_madrid()
    
    # Restar 24 horas
    desplazamiento = timedelta(hours=24)
    fecha_24_horas_antes = fecha_hora_actual - desplazamiento

    # Convertir la fecha a formato Unix
    fecha_24_horas_antes_unix = fecha_24_horas_antes.timestamp()
    fecha_hora_actual = fecha_hora_actual.timestamp()

    #dt = 1598911200   # 1 septiembre 2020 00h
    #df_final = 1664571600  # 30 septiembre 2020 23h

    dt = int(fecha_24_horas_antes_unix)   # 4 ocutbre 2022 00h
    df_final = int(fecha_hora_actual)  # 5 ocutbre 2022 00h


    url = []
    for i in range(dt, df_final + 1, 3600):
        url_1 = f"https://api.openweathermap.org/data/3.0/onecall/timemachine?lat=38.6628444&lon=-5.391886111111112&dt={i}&appid={api_key}&units=metric"
        url.append(url_1)

    querystring = {"api_key": api_key}
    lista = []

    for x in range(0,len(url),1):
        # Realiza una solicitud HTTP utilizando la API key
        response_1 = requests.get(url[x], params=querystring, verify=False, headers=headers)
        response_1.status_code == requests.codes.ok
        content_1 = response_1.json()
        lista.append(content_1)


    # Verifica si la solicitud fue exitosa
    if response_1.status_code == 200:
        # Convierte la respuesta JSON en un diccionario (si es una respuesta JSON)
        data = response_1.json()
    
        # Muestra la respuesta en la interfaz de Streamlit
        st.write("Respuesta de la API:")
        st.json(data)  # Esto muestra la respuesta en formato JSON
    else:
        st.write(f"Error en la solicitud: {response.status_code}")


    ####
    response_1.status_code == requests.codes.ok
    content_1 = response_1.json()

    df = pd.DataFrame()
    for x in range(0,len(lista) ,1):
        df_1 = pd.json_normalize(lista[x], record_path= ['data'])
        objeto_1 = [df_1, pd.DataFrame(df_1['weather'].tolist()).iloc[:, :4]]
        df_1 = pd.concat(objeto_1, axis=1)
        df_1 = pd.concat([df_1.drop([0,'weather'], axis=1), df_1[0].apply(pd.Series)], axis=1)
        #df_1['fecha'] = pd.to_datetime(df_1['dt'], unit = 's', utc=True).tz_convert('Europe/Madrid')
        df_1['fecha'] = pd.to_datetime(df_1['dt'], unit='s')
        df_1['fecha'] = df_1['fecha'].dt.tz_localize('UTC').dt.tz_convert('Europe/Madrid')  #Aplicar cambio horario
        df_1['mes'] = df_1['fecha'].dt.month
        df_1['dia'] = df_1['fecha'].dt.day
        df_1['hora'] = df_1['fecha'].dt.hour
        
        #df_1['fecha'] = df_1.apply(lambda x: datetime.fromtimestamp(x['dt']), axis = 1 )
        #df_1['mes'] = df_1.apply(lambda x: datetime.fromtimestamp(x['dt']).strftime('%m'), axis = 1 )
        #df_1['dia'] = df_1.apply(lambda x: datetime.fromtimestamp(x['dt']).strftime('%d'), axis = 1 )
        #df_1['hora'] = df_1.apply(lambda x: datetime.fromtimestamp(x['dt']).strftime('%H'), axis = 1 )
        df = pd.concat([df, df_1], axis = 'index')
    
    st.dataframe(df)

    ###Corrección de nombres manual
    df.rename(columns = {'id':'weather_id', 'main':'weather_main', 'description':'weather_description', 'icon':'weather_icon'}, inplace=True)

    #Indexamos por las variables de interés para poder juntarlo también con los históricos

    df = df[['dt','temp','pressure', 'humidity',
             'dew_point','feels_like','wind_speed', 'wind_deg',
            'clouds', 'weather_id', 'weather_main', 'weather_description', 'weather_icon']]
    
    return(df)

### Calidad de datos
def calidad_de_datos_previa(df_planta, df_meteo):
    
    ###Crear variable date en cada dataframe
    df_planta['date'] = pd.to_datetime(df_planta.date)
    df_planta = df_planta.set_index(['date'])
    
    df_meteo['date'] = pd.to_datetime(df_meteo.date)
    df_meteo = df_meteo.set_index(['date'])
    ####
    
    ####
    #Filtramos por las vbles finales de df_meteo
    df_meteo = df_meteo[['temp','pressure', 'humidity',
             'dew_point','feels_like','wind_speed', 'wind_deg',
            'clouds', 'weather_id', 'weather_main', 'weather_description', 'weather_icon']]
     
    ####
    
    ####
    ###Regularización previa 
    df_meteo = df_meteo.reset_index().drop_duplicates(subset='date', keep='first').set_index(['date'])
    df_planta = df_planta.reset_index().drop_duplicates(subset='date', keep='first').set_index(['date'])
    ####
    
    ####
    ###Gestión de nulos previa
    df_meteo = df_meteo.resample('1H').asfreq()
    
    # Seleccionar las columnas para hacer la media
    cols_media = ['temp', 'dew_point', 'feels_like',
           'pressure', 'humidity', 'wind_speed',
           'wind_deg','clouds_all']

    #Seleccionar las columnas para copiar registros
    cols_copiar = list(set(df_meteo.columns) - set(cols_media))   #Lista con el resto de variables a copiar del registro anterior

    # Obtener los índices de los nuevos registros
    new_index = df_meteo[df_meteo.isnull().all(axis=1)].index

    # Iterar sobre los índices de los nuevos registros y copiar la información del registro anterior
    for i in new_index:
        df_meteo.loc[i] = df_meteo.loc[i - pd.Timedelta('1H')]

    #Iterar sobre los índices de los nuevos registros y hacer la media de las variables de cols_media (con el método shift daba error)
    for i in new_index:
        for col in cols_media:
            df_meteo.loc[i, col] = ( (df_meteo.loc[i - pd.Timedelta('1H'), col]) + (df_meteo.loc[i + pd.Timedelta('1H'), col]) ) / 2
    ####
    
    ####
    ###Crear tablón analítico
    df = pd.merge(df_planta.reset_index(), df_meteo.reset_index(), how = 'outer', on = 'date')
    df = df.set_index(['date'])
    ####
    
    ####
    ###Corrección de nombres automática para todas las variables
    df = clean_names(df)
    ####
    
    ####
    ###Corrección de nombres manual
    df.rename(columns = {'clouds_all':'clouds'}, inplace=True)

    return(df)  


### Nueva función de calidad de datos!!
def calidad_de_datos(df):
    

    ###Filtrar por variables definitivas que han pasado el proceso de preselección de variables
    #df = df[['irradiation','t_ambient','t_module','loss_sensor_1','loss_sensor_2', 'kw_inverter','temp','humidity','pressure','wind_speed','wind_deg','rain_1h','clouds','weather_main','weather_description','weather_id','dew_point','feels_like']] 
    df = df[['irradiation','t_ambient','t_module','loss_sensor_1','loss_sensor_2', 'kw_inverter','temp','humidity','pressure','wind_speed','wind_deg','clouds','weather_main','weather_description','weather_id','dew_point','feels_like']] 

    ####
    
    ####
    ###Creación nuevas variables y corrección de tipos de variables
    #Bucle en el que creamos iterativamente las variables de fallo de conexión debidas al df_planta. 
    #Si el dato es '-' la variable asociada valdrá 1.

    for x in df.columns[0:6]:
            df['failed_connection' + '_' + x ] = 0
            df['failed_connection' + '_' + x ] = np.select([df[x] == '-'],[ 1 ], default = df['failed_connection' + '_' + x])
   
    # Iterar por las columnas relativas a df_planta y hacer select de numpy para sustituirlos por ceros y así tenerlas como variables numéricas

    for x in df.columns[0:6]:
        df[x] = np.select([df[x] == '-'],[ 0 ], default = df[x])
    ####
    
    ####
    ###Corrección tipos de datos
    df = df.astype({'irradiation':'float', 'kw_inverter':'float', 't_ambient':'float', 't_module':'float',
                    'loss_sensor_1':'float','loss_sensor_2':'float', 'pressure': 'int64', 'humidity': 'int64', 'wind_deg':'int64',
                    'clouds':'int64', 'weather_id':'int64'})
    ####
    
    ####
    ###Gestión de nulos final
    #df['rain_1h'] = df.rain_1h.fillna(0)
    
    return(df)


### Creación de variables
def crear_nuevas_variables(df):
    
    ###VARIABLES COMPONENTES FECHA: 
    #Crearemos variables de componentes de la fecha que han pasado la preselección de variables: month, hour.
    df['month'] = pd.to_numeric(df.index.month)
    df['hour'] = pd.to_numeric(df.index.hour)
    ####
    
    ####
    ###VARIABLES EXÓGENAS:   
    #Creamos variable rendimiento de los paneles solares -> 'percent_efficiency'

    fecha_instalacion = pd.to_datetime('2020-02-07 00:00:00') #Fecha de instalación

    #Crearemos variable que calcule el número de horas transcurridas desde la fecha de instalación
    df['num_hours'] = df.index - fecha_instalacion
    df['num_hours'] = df['num_hours'].apply(lambda x: x.total_seconds() / 3600)

    #El porcentaje de rendimiento de la instalación va bajando, lo expresamos a continuación:
    efficiency  = 0.0000799
    df['percent_efficiency'] = (97.5 - (efficiency * df['num_hours']))

    #Eliminamos la variable 'num_hours'
    df.drop(columns = 'num_hours', inplace = True)
    ####
    
    #### 
    ### LAGS
    #Debido a que tenemos datos de la planta pero no los tenemos en el momento en que esté en ejecución (no tenemos estos datos a futuro) 
    #Crearemos lags de estas variables a 24h ya que además el parque solar está situado en una zona en la que no hay mucha variabilidad meteorológica.
    
    #Realizamos los lags sobre las variables que han pasado la preselección de variables
    
    #Función para crear lags
    
    def creacion_lag(df, variable):
        #Crear el objeto dataframe
        lag = pd.DataFrame()

        #Crear el lag de 24 horas
        lag[variable + '_lag_'+ str(24)] = df[variable].shift(24)

        #Devuelve el dataframe de lags
        return(lag)
    
    #Aplicamos la función lag a las variables de interés
    lag_irradiation = creacion_lag(df = df, variable = 'irradiation')
    lag_t_ambient = creacion_lag(df = df, variable = 't_ambient')
    lag_t_module = creacion_lag(df = df, variable = 't_module')
    lag_loss_sensor_1 = creacion_lag(df = df, variable = 'loss_sensor_1')
    lag_loss_sensor_2 = creacion_lag(df = df, variable = 'loss_sensor_2')
    lag_failed_connection_irradiation = creacion_lag(df = df, variable = 'failed_connection_irradiation')
    ####
    
    ####
    ###VENTANAS MÓVILES -> Media móvil
    #Vamos a crear las variables móviles aplicando la media móvil sobre la variable target "kw_inverter" en el rango de 24 horas.
    #Como esta es la variable target, necesitaremos también hacer ventanas móviles de las variables que recogen el fallo de conexión de la variable target. Esta es la variable "failed_connection_kw_inverter".

    #Función media móvil
    def media_movil(df, variable, num_periodos):

        df_media_movil = pd.DataFrame()

        for x in range(2,num_periodos+1):   #Se empieza por 2 ya que para que la media tenga sentido se necesitan 2 datos.
            df_media_movil[variable + '_mm_' + str(x)] = df[variable].shift(1).rolling(x).mean()  #La ventana móvil hace desde la hora anterior a 24 horas antes 

        #Devuelve el dataframe de media móvil
        return(df_media_movil)
   
    #Aplicamos la función a variables
    media_movil_target = media_movil(df = df, variable = 'kw_inverter',  num_periodos = 24)
    media_movil_failed_connection_target = media_movil(df = df, variable = 'failed_connection_kw_inverter',  num_periodos = 24)
    ####
    
    ####
    ### Unir todos los dataframes
    df_union = pd.concat([df,lag_irradiation, lag_t_ambient, lag_t_module, lag_loss_sensor_1, lag_loss_sensor_2,
                      lag_failed_connection_irradiation, media_movil_target, media_movil_failed_connection_target], axis = 1)    
    
    ### Eliminamos nulos recién creados
    df_union.dropna(inplace=True)
    
    ### Eliminar variables que no se utilizarán para modelizar pero han servido para la creación de variables
    vbles_a_eliminar = ['irradiation','t_ambient', 't_module','loss_sensor_1', 'loss_sensor_2','failed_connection_irradiation', 'failed_connection_t_ambient', 'failed_connection_t_module', 'failed_connection_loss_sensor_1', 'failed_connection_loss_sensor_2']
    df_union.drop(columns = vbles_a_eliminar, inplace=True)
    ####
    
    ####    
    #El resto de variables se han creado en la calidad de datos y las variables de encoding se crearán en la función de transfromación

    return(df_union)


### Transformación de variables
def transformacion_de_variables(x, target = None, opcion = 'entrenamiento'):
    #Debido a que se utiliza scikit learn para crear variables, se crea una función a parte.
    #Se utilizará la función tanto para el entrenamiento como en ejecución
    
    x.reset_index(inplace = True)
    
    #Gestión previa de encoding
    
    ###One hot encoding
    vbles_ohe = ['weather_main', 'weather_description']
    
    if opcion == 'entrenamiento':
        
        #Si está en entrenamiento aplica fit_transform y guarda el encoder
        ohe = OneHotEncoder(sparse = False, handle_unknown = 'ignore')
        ohe_x = ohe.fit_transform(x[vbles_ohe])
        ohe_x = pd.DataFrame(ohe_x, columns = ohe.get_feature_names_out())
        with open('ohe_retail.pickle', mode = 'wb') as file:
           pickle.dump(ohe, file)
            
    else:
        
        #Si está en ejecución recupera el guardado y solo aplica transform
        with open('ohe_retail.pickle', mode='rb') as file:
            ohe = pickle.load(file)
        ohe_x = ohe.transform(x[vbles_ohe])
        ohe_x = pd.DataFrame(ohe_x, columns = ohe.get_feature_names_out())

    ###Target encoding -> Al utilizar target encoding necesitaremos pasarle la vble target ya que este encoding mira la penetración media de la target en cada vble predictora.
    #La vble target solamente será necesaria en la opción de entrenamiento.
    vbles_te = ['weather_main', 'weather_description']    
    
    if opcion == 'entrenamiento':
        #La vble target debe tener los mismos registros que x:
        target.reset_index(inplace = True, drop = True)
        target = target.loc[target.index.isin(x.index)]
        
        #Como está en la opción de entrenamiento, aplicará fit_transform y guardará el encoder en disco
        te = TargetEncoder(min_samples_leaf = 100, return_df = False)
        te_x = te.fit_transform(x[vbles_te], y = target)
        nombres_te = [variable + '_te' for variable in vbles_te]
        te_x = pd.DataFrame(te_x, columns = nombres_te)
        
        with open('te_retail.pickle', mode = 'wb') as file:
           pickle.dump(te, file)
        
    else:
        #Como está en ejecución recuperará el guardado de disco y solo aplicará transform
        
        with open('te_retail.pickle', mode = 'rb') as file:
            te = pickle.load(file)
            
        te_x = te.transform(x[vbles_te])
        nombres_te = [variable + '_te' for variable in vbles_te]
        te_x = pd.DataFrame(te_x, columns = nombres_te)
    
    
    #Fase final
    #Se eliminan las vbles originales
    x = x.drop(columns=['weather_main', 'weather_description'])
    #Se juntan todos los dataframes
    x = pd.concat([x, ohe_x, te_x], axis = 1).set_index('date')

    #Devolver dataframe
    return(x)
    
### Ejecución
def ejecucion(df):
    
    #Forecast de una hora. Posteriormente se ejecutará el forecast recursivo
    #La entrada es el dataset que va a predecir
    #Estructura de datos de producción
    #El sistema necesitará nutrirse de datos de 24 horas previas debido a las variables que se han construido
    
    #Carga del modelo

    with open('modelo.pickle', mode='rb') as file:
       modelo_cargado = pickle.load(file)
    
    #Creación de dataframe en blanco con las siguientes variables para ir rellenando
    df_prediccion = pd.DataFrame(columns=['date','kw_inverter','prediccion'])
    
    modelo = modelo_cargado
    variables = modelo.feature_names_in_
    target = 'kw_inverter'

    x = df.drop(columns= ['kw_inverter']).copy()
    y = df['kw_inverter'].copy()
        
    date = df.reset_index().copy()
    date = date['date'].values
    
    #Ejecutar fución de transformacion_de_variables
    x = transformacion_de_variables(x, opcion = 'ejecucion')
    
    #Selección de las variables utilizadas para modelo entrenado
    x = x[variables]    
    
    #Cálculo de las predicciones
    predicciones = pd.DataFrame(data={'date': date,'kw_inverter': y,'prediccion': modelo.predict(x)})

    ###Calidad de datos finales
    #Quitar el índice
    predicciones = predicciones.reset_index(drop=True) 

    #Reemplazar valores negativos a cero
    condicion = predicciones['prediccion'] < 0
    predicciones['prediccion'] = np.select( [ condicion ],[0], default = predicciones['prediccion'] )
     
    #Ajustar datos para que entre las 11 pm y 5 am las predicciones tengan valor 0
    predicciones['date_datetime'] = pd.to_datetime(predicciones['date'], unit = 's')
    predicciones['date_hour'] = predicciones['date_datetime'].dt.hour
    predicciones['prediccion'] = np.select( [ ( predicciones['date_hour'] >= 0 ) & (predicciones['date_hour'] <= 5) | (predicciones['date_hour'] == 23) | (predicciones['date_hour'] == 22) ],[0], default = predicciones['prediccion'] )
    predicciones = predicciones.drop(columns = ['date_datetime','date_hour'])
    
    # Redondear valores de variable a predecir al segundo decimal
    predicciones['prediccion'] = predicciones['prediccion'].round(2)
    
    ###Concatenar dataframes
    df_prediccion = pd.concat([df_prediccion, predicciones])
    
    #El modelo necesita en este proceso solamente la predicción de la hora siguiente. Por lo que se queda con la hora mínima
    df_prediccion = df_prediccion.loc[df_prediccion.index == df_prediccion.index.min()]
    
    #Salida del dataframe de predicción de 1 hora
    return(df_prediccion)

def forecast_recursivo(x):
    
    #Debido a que los modelos de ML predicen solamente un dato a futuro necesitamos aplicar predicción multipaso. Se utilizará la aproximación recursiva.
    #Se aplica forecast recursivo a 24 horas vista.
    #La entrada es el df que se encuentra en producción
     
    for i in range(0,24):  #se ejecuta el bucle 24 veces
        df1 = calidad_de_datos(x) 
        df2 = crear_nuevas_variables(df1)
        
        #Cálculo de la predicción
        df_ejecucion = ejecucion(df2)

        #Actualizar el registro de kw_inverter con la predicción
        #x.loc[(x.index.isin(df_ejecucion.date)),'kw_inverter'] = df_ejecucion.prediccion
        x.loc[x.index.isin(df_ejecucion.date.dt.floor('H')), 'kw_inverter'] = df_ejecucion.prediccion.values

        #Eliminar el registro más antiguo de x
        x = x.loc[x.index != x.index.min()]
        
    return(x)
    
### Preprocesamiento previo
def preprocesamiento_datos(fecha_hora_actual, dataset_irrad_energia, dataset_polvo, dataset_temperatura, dataset_openweathermap, dataset_futuro_openweathermap):
    
    # Extraer el año, el mes, el día y la hora
    year = fecha_hora_actual.year
    month = fecha_hora_actual.month
    day = fecha_hora_actual.day
    hour = fecha_hora_actual.hour
    ####

    ####
    # Restar 24 horas
    desplazamiento = timedelta(hours=24)
    fecha_24_horas_antes = fecha_hora_actual - desplazamiento

    # Extraer el año, el mes, el día y la hora de la fecha 24 horas antes
    year_previous = fecha_24_horas_antes.year
    month_previous = fecha_24_horas_antes.month
    day_previous = fecha_24_horas_antes.day
    hour_previous = fecha_24_horas_antes.hour

    fecha_24_horas_antes = datetime(year_previous, month_previous, day_previous, hour_previous)

    # Generar el rango de fechas a pasado con el intervalo deseado (por ejemplo, cada hora)
    rango_fechas_pasado = pd.date_range(start= fecha_24_horas_antes + timedelta(hours=1), end= fecha_hora_actual, freq='H')
    ####

    ####
    # Sumar 24 horas
    desplazamiento = timedelta(hours=24)
    fecha_24_horas_futuro = fecha_hora_actual + desplazamiento

    # Generar el rango de fechas con el intervalo deseado (por ejemplo, cada hora)
    rango_fechas_futuro = pd.date_range(start=fecha_hora_actual + timedelta(hours=1), end=fecha_24_horas_futuro, freq='H')

    ####

    ####

    ###Modificación de la estructura

    ## Dataset irradiación energia
    dataset_irrad_energia= dataset_irrad_energia.T.reset_index()
    dataset_irrad_energia = dataset_irrad_energia.loc[2:]
    dataset_irrad_energia = dataset_irrad_energia.rename(columns = {'index': 'date', 0: 'irradiation', 1: 'kw_inverter'})
    dataset_irrad_energia['date'] = pd.to_datetime(dataset_irrad_energia.date, dayfirst = True )
    dataset_irrad_energia = dataset_irrad_energia.set_index(['date'])
    dataset_irrad_energia = dataset_irrad_energia.loc[rango_fechas_pasado]   #Indexamos por el periodo analizado
    dataset_irrad_energia = dataset_irrad_energia.set_index(dataset_irrad_energia.index.rename('date'))  #En la ejecución anterior se perdía el nombre del índice
    dataset_irrad_energia = dataset_irrad_energia.sort_index(ascending = True) #Ordenamos temporalmente porque vemos que hay fallos en la ordenación
    
    ###

    ###
    ## Dataset temperatura
    dataset_temperatura= dataset_temperatura.T.reset_index()
    dataset_temperatura = dataset_temperatura.loc[2:]
    dataset_temperatura = dataset_temperatura.rename(columns = {'index': 'date', 0: 't_ambient', 1: 't_module'})
    dataset_temperatura['date'] = pd.to_datetime(dataset_temperatura.date, dayfirst = True)
    dataset_temperatura = dataset_temperatura.set_index(['date'])
    dataset_temperatura = dataset_temperatura.loc[rango_fechas_pasado]   #Indexamos por el periodo analizado
    dataset_temperatura = dataset_temperatura.set_index(dataset_temperatura.index.rename('date'))  #En la ejecución anterior se perdía el nombre del índice
    dataset_temperatura = dataset_temperatura.sort_index(ascending = True)  #Ordenamos temporalmente porque vemos que hay fallos en la ordenación
    ###

    ###
    ## Dataset sensor de polvo
    dataset_polvo= dataset_polvo.T.reset_index()
    dataset_polvo = dataset_polvo.loc[2:]
    dataset_polvo = dataset_polvo.rename(columns = {'index': 'date', 0: 'loss_sensor_1', 1: 'loss_sensor_2'})
    dataset_polvo['date'] = pd.to_datetime(dataset_polvo.date, dayfirst = True)
    dataset_polvo = dataset_polvo.set_index(['date'])
    dataset_polvo = dataset_polvo.loc[rango_fechas_pasado]   #Indexamos por el periodo analizado
    dataset_polvo = dataset_polvo.set_index(dataset_polvo.index.rename('date'))  #En la ejecución anterior se perdía el nombre del índice
    dataset_polvo = dataset_polvo.sort_index(ascending = True)  #Ordenamos temporalmente porque vemos que hay fallos en la ordenación
    ###

    ###
    ## Dataset OpenWeatherMap
    dataset_openweathermap['date'] = dataset_openweathermap.apply(lambda x: datetime.fromtimestamp(x['dt']), axis = 1 )
    #dataset_openweathermap = dataset_openweathermap.drop(columns = ['dt','dt_iso','timezone','city_name','lat','lon'])  #Quitar vbles que no interesan
    dataset_openweathermap = dataset_openweathermap.drop(columns = ['dt'])  #Quitar vbles que no interesan
    dataset_openweathermap = dataset_openweathermap.set_index(['date'])
    dataset_openweathermap = dataset_openweathermap.loc[rango_fechas_pasado]   #Indexamos por el periodo analizado
    dataset_openweathermap = dataset_openweathermap.set_index(dataset_openweathermap.index.rename('date'))  #En la ejecución anterior se perdía el nombre del índice
    dataset_openweathermap = dataset_openweathermap.sort_index(ascending = True) #Ordenamos temporalmente porque vemos que hay fallos en la ordenación
    ###

    ###
    ## Dataset futuro OpenWeatherMap
    dataset_futuro_openweathermap['date'] = dataset_futuro_openweathermap.apply(lambda x: datetime.fromtimestamp(x['dt']), axis = 1 )
    #dataset_futuro_openweathermap = dataset_futuro_openweathermap.drop(columns = ['dt','dt_iso','timezone','city_name','lat','lon'])  #Quitar vbles que no interesan
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.drop(columns = ['dt'])  #Quitar vbles que no interesan
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.set_index(['date'])
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.loc[rango_fechas_futuro]   #Indexamos por el periodo analizado
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.set_index(dataset_futuro_openweathermap.index.rename('date'))  #En la ejecución anterior se perdía el nombre del índice
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.sort_index(ascending = True) #Ordenamos temporalmente porque vemos que hay fallos en la ordenación

    ###Crear variable date en cada dataframe
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.reset_index()
    dataset_futuro_openweathermap['date'] = pd.to_datetime(dataset_futuro_openweathermap.date)
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.set_index(['date'])

    #Filtramos por las vbles finales de df_meteo
    dataset_futuro_openweathermap = dataset_futuro_openweathermap[['temp','pressure', 'humidity',
                 'dew_point','feels_like','wind_speed', 'wind_deg',
                'clouds', 'weather_id', 'weather_main', 'weather_description', 'weather_icon']]

    ###Regularización previa 
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.reset_index().drop_duplicates(subset='date', keep='first').set_index(['date'])

    ###Gestión de nulos previa
    dataset_futuro_openweathermap = dataset_futuro_openweathermap.resample('1H').asfreq()

    # Seleccionar las columnas para hacer la media
    cols_media = ['temp', 'dew_point', 'feels_like',
               'pressure', 'humidity', 'wind_speed',
               'wind_deg','clouds']

    #Seleccionar las columnas para copiar registros
    cols_copiar = list(set(dataset_futuro_openweathermap.columns) - set(cols_media))   #Lista con el resto de variables a copiar del registro anterior

    # Obtener los índices de los nuevos registros
    new_index = dataset_futuro_openweathermap[dataset_futuro_openweathermap.isnull().all(axis=1)].index

    # Iterar sobre los índices de los nuevos registros y copiar la información del registro anterior
    for i in new_index:
        dataset_futuro_openweathermap.loc[i] = dataset_futuro_openweathermap.loc[i - pd.Timedelta('1H')]

    #Iterar sobre los índices de los nuevos registros y hacer la media de las variables de cols_media (con el método shift daba error)
    for i in new_index:
        for col in cols_media:
            dataset_futuro_openweathermap.loc[i, col] = ( (dataset_futuro_openweathermap.loc[i - pd.Timedelta('1H'), col]) + (dataset_futuro_openweathermap.loc[i + pd.Timedelta('1H'), col]) ) / 2

    ##Corrección de nombres automática para todas las variables
    dataset_futuro_openweathermap = clean_names(dataset_futuro_openweathermap)

    ##Corrección de nombres manual
    #dataset_futuro_openweathermap.rename(columns = {'clouds_all':'clouds'}, inplace=True)

    ###

    ###

    ##Creación de 2 dataframes: df_planta, df_meteo

    df = pd.merge(dataset_irrad_energia.reset_index(), dataset_temperatura.reset_index(), how = 'outer', on = 'date' )
    df_planta = pd.merge(df, dataset_polvo.reset_index(), how = 'outer', on = 'date' )
    df_planta = df_planta.set_index(['date'])
    df_planta = df_planta.sort_index(ascending = True) #Ordenamos índice por si acaso
    df_planta = df_planta.reset_index()
    df_planta = df_planta[['date', 'irradiation', 'kw_inverter', 't_ambient', 't_module','loss_sensor_1', 'loss_sensor_2']]  #Asegurar las columnas por si en un futuro añadieran



    df_meteo = dataset_openweathermap.copy()
    df_meteo = df_meteo.sort_index(ascending = True)   #Ordenamos índice por si acaso
    df_meteo = df_meteo.reset_index()
    df_meteo = df_meteo[['date','temp','pressure', 'humidity',
                 'dew_point','feels_like','wind_speed', 'wind_deg',
                'clouds', 'weather_id', 'weather_main', 'weather_description', 'weather_icon']] #Asegurar las columnas por si en un futuro añadieran

    #Salida de datos
    return(df_planta, df_meteo, dataset_futuro_openweathermap)


### Ejecución del modelo
def ejecuccion_de_modelo(fecha_hora_actual, dataset_irrad_energia, dataset_polvo, dataset_temperatura, dataset_openweathermap, dataset_futuro_openweathermap):
    
    ### LLAMADAS A LAS FUNCIONES 
    
    #Ejecutar función preprocesamiento_datos y obtener una tupla
    resultado = preprocesamiento_datos(fecha_hora_actual, dataset_irrad_energia, dataset_polvo, dataset_temperatura, dataset_openweathermap, dataset_futuro_openweathermap)

    # Tuple unpacking para acceder a todos los dataframes
    df_planta, df_meteo, dataset_futuro_openweathermap = resultado


    ### DATAFRAME CON HISTÓRICO DE DATOS
    #Ejecutar función calidad_de_datos_previa
    df_historico = calidad_de_datos_previa(df_planta, df_meteo)

    ### CREACIÓN DATAFRAME CON DATOS FUTUROS

    df_historico = df_historico.reset_index()

    # Generar un rango de fechas adicionales con 24 horas
    rango_fechas = pd.date_range(start= fecha_hora_actual + pd.DateOffset(hours=1), end= fecha_hora_actual + pd.DateOffset(hours=24), freq='H')

    # Crear un DataFrame con las fechas adicionales
    df_futuro = pd.DataFrame({'date': rango_fechas})

    #Columnas a poner referentes al df_planta
    columnas_a_poner = ['irradiation', 'kw_inverter', 't_ambient', 't_module',
                        'loss_sensor_1', 'loss_sensor_2']

    df_futuro = pd.concat([df_futuro, pd.DataFrame(columns = columnas_a_poner)] ) #sort=False

    # Rellenar con ceros -> Estas son las vbles pertenecientes a la planta y no las tendremos a futuro por lo que se rellenan con ceros
    df_futuro = df_futuro.fillna(0)

    #Juntar con dataset_futuro_openweathermap para obtener el df a futuro
    df_futuro = pd.merge(df_futuro, dataset_futuro_openweathermap, how = 'left', on = 'date' )


    #Reordenamos columnas para que tengan el mismo orden que df_historico
    df_futuro = df_futuro[['date', 'irradiation', 'kw_inverter', 't_ambient', 't_module',
           'loss_sensor_1', 'loss_sensor_2', 'temp', 'pressure', 'humidity',
           'dew_point', 'feels_like', 'wind_speed', 'wind_deg', 'clouds',
           'weather_id', 'weather_main', 'weather_description', 'weather_icon']]
    df_futuro


    #### TABLÓN ANALÍTICO
    ## Creamos el dataframe necesario para la recursividad concatenando el df_historico y df_futuro
    df_tablon = pd.concat([df_historico, df_futuro], axis = 'index') 
    df_tablon = df_tablon.set_index('date')

    #Lanzar la predicción
    df_forecast = forecast_recursivo(df_tablon)
    
    df_historico = df_historico.set_index('date')

    return(df_forecast,df_historico)
    

