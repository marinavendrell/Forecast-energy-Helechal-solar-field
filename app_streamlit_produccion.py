import streamlit as st
from codigo_de_ejecucion_para_produccion import *

import folium

from streamlit_folium import folium_static
import streamlit.components.v1 as components
from streamlit_echarts import st_echarts
from streamlit_lottie import st_lottie

import json

from branca.element import Figure

import plotly.graph_objects as go

import statistics

from io import BytesIO
import base64

import pytz

import requests

import arrow


### CONFIGURACIÓN DE LA PÁGINA

st.set_page_config( page_title='Forecasting solar energy',
                    page_icon = 'logo.png',
                    layout= 'wide',
                    initial_sidebar_state="auto",
                    menu_items=None)

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)



### SIDEBAR

with st.sidebar:
    st.image('foto_parque_solar.png')

    
    # INPUTS
    dataset_carga_planta = st.file_uploader('Select data from the solar field')
    
    
    #Calculamos la fecha y hora actuales y 24h previas. Esta será la hora de Madrid, España
    
    def obtener_fecha_hora_madrid():
        zona_horaria_madrid = pytz.timezone('Europe/Madrid')
        fecha_hora_madrid = datetime.now(zona_horaria_madrid)
        return fecha_hora_madrid.replace(minute=0, second=0, microsecond=0)
    
    # Obtener la fecha y hora de Madrid
    #fecha_hora_actual = obtener_fecha_hora_madrid()
    fecha_hora_actual = arrow.now('Europe/Madrid')
    

    # Obtén la fecha y hora de hace 24 horas en la misma zona horaria
    fecha_24_horas_antes = fecha_hora_actual.shift(hours=-24)

    
    # 23 horas antes
    #desplazamiento = timedelta(hours=24)
    #fecha_24_horas_antes = fecha_hora_actual - desplazamiento
    
    # Convierte ambas fechas a objetos datetime de Python
    fecha_hora_actual = fecha_hora_actual.datetime
    fecha_24_horas_antes = fecha_24_horas_antes.datetime

    # Elimina la información de zona horaria (convierte a objeto naive)
    fecha_hora_actual = fecha_hora_actual.replace(tzinfo=None)
    fecha_24_horas_antes = fecha_24_horas_antes.replace(tzinfo=None)

    # Crea un nuevo objeto datetime con solo año, mes, día y hora
    fecha_hora_actual = datetime(
                            year=fecha_hora_actual.year,
                            month=fecha_hora_actual.month,
                            day=fecha_hora_actual.day,
                            hour=fecha_hora_actual.hour
                        )

    # Crea un nuevo objeto datetime con solo año, mes, día y hora para 24 horas antes
    fecha_24_horas_antes = datetime(
                            year=fecha_24_horas_antes.year,
                            month=fecha_24_horas_antes.month,
                            day=fecha_24_horas_antes.day,
                            hour=fecha_24_horas_antes.hour
                        )

### PARTE CENTRAL APP
st.title('Forecasting solar energy production')


### CÁLCULOS

#dataset_irrad_energia = None
#dataset_polvo = None
#dataset_openweathermap = None
#dataset_futuro_openweathermap = None


if st.sidebar.button('CALCULATE FORECAST'):   # Solamente se ejecuta cuando el usuario hace click en el botón
    
    
    with st.spinner("Executing AI model. Wait a few seconds to see the results..."):
        
        # Creamos dataframes     
        
        @st.cache_data()
        def carga_datos_planta(dataset_carga_planta):
            if dataset_carga_planta is not None:
                dataset_carga_planta = pd.read_excel(dataset_carga_planta)
            else:
                st.stop()
            return(dataset_carga_planta)



        #Creamos función para cambiar color al texto utilizando html
        def color_de_texto(wgt_txt, wgt_value = None, wch_title_colour='#000000', wch_value_colour='#000000'):
            htmlstr = f"""<script>var elements = window.parent.document.querySelectorAll('*'), i;
                            for (i = 0; i < elements.length; ++i) {{
                                if (elements[i].innerText == "{wgt_txt}") {{
                                    elements[i].style.color = "{wch_title_colour}";
                                    elements[i].nextSibling.style.color = "{wch_value_colour}";
                                }}
                            }}</script>"""

            components.html(htmlstr, height=0, width=0)



        #Ejecutar funciones
   
        dataset_carga_planta = carga_datos_planta(dataset_carga_planta)
               
        dataset_openweathermap = conexion_openweathermap_pasado(fecha_hora_actual,fecha_24_horas_antes)
                
        dataset_futuro_openweathermap = conexion_openweathermap_futuro()
        
        
        #Separamos los datos que provienen de la planta en varios dataframes y tenermos que resetear los índice para que el código funcione
        
        dataset_irrad_energia = dataset_carga_planta[(dataset_carga_planta['Name'] == 'Helechal (ES).Plant.Irradiation_average') | (dataset_carga_planta['Name'] == 'Helechal (ES).Plant.Power by Inverter')].reset_index(drop=True)
        
        dataset_polvo = dataset_carga_planta[(dataset_carga_planta['Name'] == 'Helechal (ES).Dust_IQ.01.Soiling Loss Sensor 1')|(dataset_carga_planta['Name'] == 'Helechal (ES).Dust_IQ.01.Soiling Loss Sensor 2')].reset_index(drop=True)

        dataset_temperatura = dataset_carga_planta[(dataset_carga_planta['Name'] == 'Helechal (ES).Meteo.z.bloxx.Ambient') | (dataset_carga_planta['Name'] == 'Helechal (ES).Meteo.z.bloxx.Module')].reset_index(drop=True)
        
        ###
        
        
        ###
        # Comprobamos que están todos los datos introducidos. Para ello haremos una primera comprobación
        
        ## Dataset irradiación energia
        df_prueba = dataset_irrad_energia.T.reset_index()
        df_prueba = df_prueba.loc[2:]
        df_prueba = df_prueba.rename(columns = {'index': 'date', 0: 'irradiation', 1: 'kw_inverter'})
        df_prueba['date'] = pd.to_datetime(df_prueba.date, dayfirst = True )
        df_prueba = df_prueba.set_index(['date'])
        df_prueba = df_prueba.set_index(df_prueba.index.rename('date'))  #En la ejecución anterior se perdía el nombre del índice
        df_prueba = df_prueba.sort_index(ascending = True) #Ordenamos temporalmente porque vemos que hay fallos en la ordenación
        df_prueba = df_prueba.reset_index()
        
        #fecha_24_horas_antes
        #fecha_hora_actual

        # Verificar las fechas
        fecha_inicial_df = pd.to_datetime(df_prueba['date']).min()
        fecha_final_df = pd.to_datetime(df_prueba['date']).max()

        # Comprobar las condiciones y mostrar mensajes
        if (fecha_inicial_df + timedelta(hours=1)) > fecha_24_horas_antes:
            st.warning(f"⚠️There is a **lack of data** provided from the solar field. Check that the information uploaded in the application is from **({(fecha_24_horas_antes + timedelta(hours=1)).strftime('%d-%m-%Y at %Hh')})** to **({fecha_hora_actual.strftime('%d-%m-%Y at %Hh')})**, all period included otherwise the application will not work. **Afterwards, try uploading it again.**")   
            st.stop()

        if fecha_final_df < fecha_hora_actual:
            st.warning(f"⚠️There is a **lack of data** provided from the solar field. Check that the information uploaded in the application is from **({(fecha_24_horas_antes + timedelta(hours=1)).strftime('%d-%m-%Y at %Hh')})** to **({fecha_hora_actual.strftime('%d-%m-%Y at %Hh')})**, all period included otherwise the application will not work. **Afterwards, try uploading it again.**")
            st.stop()
       
        del df_prueba, fecha_inicial_df, fecha_final_df
        
        # Terminado este proceso previo, procedemos a ejecutar el modelo
        ###
        
        
        
        ###   
        
        #Ejecuta el modelo    
        df_forecast, df_historico = ejecuccion_de_modelo(fecha_hora_actual, dataset_irrad_energia, dataset_polvo, dataset_temperatura, dataset_openweathermap, dataset_futuro_openweathermap)

        # Obtener el último registro del df_historico
        ultimo_registro = df_historico.iloc[-1:]

        # Concatenar el último registro al comienzo del df_forecast para que el gráfico salga concatenado
        df_forecast_grafico = pd.concat([ultimo_registro, df_forecast])

        #En df creado de df_forecast_grafico cambiaremos las unidades de wind_speed de m/s a km/h
        df_forecast['wind_speed'] = round(df_forecast['wind_speed'] * 3.6, 2)   #Pasa de m/s a Km/h y redondeamos a 2 decimales

        #Calculamos el total de energía producida en el forecasting   
        kwh_total = df_forecast['kw_inverter'].sum()
        MWh_forecasting = kwh_total / 1000



        #Gráfico interactivo

        fig = go.Figure()

        ### FORECASTING ENERGY
        fig.add_trace(go.Scatter(
                          x=df_forecast_grafico.index,
                          y=df_forecast_grafico['kw_inverter'],
                          mode="lines+markers",
                          line=dict(color='#4B8A8A', dash='dashdot'),  #1F354F
                          marker=dict(size=4, color='#1F354F', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#1F354F")),
                          name="Forecasting",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(143, 186, 235, 0.3)'  # Color azul semitransparente
                        ))


        #Históricos
        fig.add_trace(go.Scatter(
                                 x=df_historico.index, 
                                 y=df_historico["kw_inverter"],
                                 mode="lines+markers",
                                 line=dict(width=1, color='#808080'),
                                 marker=dict(size=4, color='#808080', symbol='circle'),
                                 hoverlabel=dict(font=dict(color="#808080")),
                                 fill='tozeroy',  # Rellena el área bajo la curva
                                 fillcolor='rgba(220, 220, 220, 0.3)',  # Gris muy claro y semitransparente
                                 name="Historical"
                                ))



        # Actualizar las etiquetas de los puntos
        fig.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>KWh</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )

        # Obtener la posición x del final de los datos históricos
        x_final_datos_historicos = df_historico.index[-1]

        # Agregar la línea vertical divisoria
        fig.add_vline(x=x_final_datos_historicos, line=dict(color='#666666',  width=2, dash='dot'))

        #Agregar mensaje encima de línea divisoria
        fig.add_annotation(
            x=x_final_datos_historicos,
            y=2,
            text="Actual hour",
            showarrow=True,
            font=dict(color='#666666'),
            bgcolor='white',
            bordercolor='#666666',
            borderwidth=1
                          )

        fig.update_layout(
                           #title='Forecast of energy production',
                           xaxis_title="Date",
                           yaxis_title="KWh"
                        )

        ###
        
        ###      

        ### PRECIO FORECASTING
        
        #Conectaremos con la página web Omie a través de un paquete de python y calcularemos el precio de los KWh generados.
        
        #Primero arreglaremos los datos que nos vienen del paquete

        #fecha_hora_actual = dt.datetime(2023, 8, 2)


        # Sumar 24 horas
        desplazamiento = timedelta(hours=24)
        fecha_24_horas_futuro = fecha_hora_actual + desplazamiento

        # Obtener el año como una cadena de texto
        anyo = str(fecha_hora_actual.year)

        # Obtener el mes como una cadena de texto con formato 'MM'
        mes = f"{fecha_hora_actual.month:02d}"

        # Obtener el día como una cadena de texto con formato 'DD'
        dia = f"{fecha_hora_actual.day:02d}"

        # Obtener el año final como una cadena de texto
        anyo_final = str(fecha_hora_actual.year)

        # Obtener el mes final como una cadena de texto con formato 'MM'
        mes_final = f"{fecha_hora_actual.month:02d}"

        # Obtener el día final como una cadena de texto con formato 'DD'
        dia_final = f"{fecha_hora_actual.day:02d}"


        url_inicial = f"https://www.omie.es/sites/default/files/dados/AGNO_{anyo}/MES_{mes}/TXT/INT_PBC_EV_H_1_{dia}_{mes}_{anyo}_{dia}_{mes}_{anyo}.TXT"
        url_final = f"https://www.omie.es/sites/default/files/dados/AGNO_{anyo_final}/MES_{mes_final}/TXT/INT_PBC_EV_H_1_{dia_final}_{mes_final}_{anyo_final}_{dia_final}_{mes_final}_{anyo_final}.TXT"


        url = []
        url.append(url_inicial)
        url.append(url_final)


        # Leer los datos desde la URL y crear un DataFrame
        #df = pd.read_csv(url[0], sep=";", encoding="ISO-8859-1", skiprows=2)



        df = pd.DataFrame()

        for url_actual in url:

            # Leer los datos desde la URL actual y crear un DataFrame
            df_actual = pd.read_csv(url_actual, sep=";", encoding="ISO-8859-1", skiprows=2)
            df_actual = df_actual[df_actual['Unnamed: 0'] == 'Precio marginal en el sistema español (EUR/MWh)']
            df_actual = df_actual.iloc[:,0:25]
            df_actual = df_actual.drop(columns = ['Unnamed: 0'])

            # Concatenar el DataFrame actual a df
            df = pd.concat([df, df_actual], ignore_index=True)




        # Crear una columna 'date' en el DataFrame
        df['date'] = None

        # Asignar el valor de fecha_hora_actual a la columna 'date' en la primera iteración
        df.loc[0, 'date'] = fecha_hora_actual.strftime('%Y-%m-%d')

        # Asignar el valor de fecha_24_horas_futuro a la columna 'date' en la segunda iteración
        df.loc[1, 'date'] = fecha_24_horas_futuro.strftime('%Y-%m-%d')

        # Mover la columna 'date' a la primera posición del DataFrame
        df.insert(0, 'date', df.pop('date'))

        # Convertimos la columna 'DATE' al tipo datetime
        df_date = df.copy()
        df_date['date'] = pd.to_datetime(df['date'])

        # Creamos una lista para almacenar las horas del día generadas
        horas_del_dia = []

        # Iteramos por cada fecha única en el DataFrame original
        for fecha in df_date['date'].unique():
            # Generamos un rango de horas del día para la fecha actual
            fecha_siguiente = fecha + pd.DateOffset(days=1)
            horas_del_dia_fecha = pd.date_range(start=fecha, end=fecha_siguiente, freq='H', closed='left')
            # Extendemos la lista con las horas del día generadas para la fecha actual
            horas_del_dia.extend(horas_del_dia_fecha)

        # Creamos un DataFrame con las horas del día
        df_date = pd.DataFrame({'date': horas_del_dia})

        # Lista para almacenar los registros transpuestos
        registros_transpuestos = []

        df = df.drop(columns = ['date'])
        # Iteramos por cada registro (fila) en el DataFrame
        for index, row in df.iterrows():
            # Transponemos el registro actual y lo almacenamos como una Serie
            registro_transpuesto = row.reset_index(drop=True)
            registro_transpuesto = registro_transpuesto.rename('Valor')
            registros_transpuestos.append(registro_transpuesto)

        # Concatenamos las Series transpuestas en un nuevo DataFrame
        EUR_MWh = pd.concat(registros_transpuestos, axis=0, ignore_index=True)

        # Convertimos la Serie en un DataFrame con una columna llamada 'Valor'
        EUR_MWh = EUR_MWh.to_frame(name='€_MWh')
        EUR_MWh['€_MWh'] = EUR_MWh['€_MWh'].str.replace(',', '.')
        EUR_MWh = pd.to_numeric(EUR_MWh['€_MWh'], errors='coerce')        
        
        
        df_precio = pd.concat([df_date, EUR_MWh], axis = 1)
        df_precio['€_KWh'] = df_precio['€_MWh']/1000
              

        #Juntamos el dataframe del forecast de energía con el dataframe creado de precio
        df_final_omie = pd.merge(df_forecast['kw_inverter'].reset_index(), df_precio, how = 'left', on = ['date'] )
        
        # Primero, convierte las columnas a numéricas
        df_final_omie['€_KWh'] = pd.to_numeric(df_final_omie['€_KWh'], errors='coerce')
        df_final_omie['kw_inverter'] = pd.to_numeric(df_final_omie['kw_inverter'], errors='coerce')

        df_final_omie['€'] = round(df_final_omie['€_KWh'] * df_final_omie['kw_inverter'], 2)
        
        
        #Calculamos el precio total de energía producida en el forecasting   
        euros_total = df_final_omie['€'].sum()       
        
        
        #Gráfico interactivo con el precio

        fig_precio = go.Figure()

        ### Price forecasting
        fig_precio.add_trace(go.Scatter(
                          x=df_final_omie.date,
                          y=df_final_omie['€'],
                          mode="lines+markers",
                          line=dict(color='#808000', dash='dashdot'),  
                          marker=dict(size=4, color='#3B5323', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#556B2F")),
                          name="Price",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(133, 153, 0, 0.1)'  # Color verde oliva claro semitransparente
                        )) 

        # Actualizar las etiquetas de los puntos
        fig_precio.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>€</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )

        fig_precio.update_layout(
                           #title='Forecast of energy production',
                           xaxis_title="Date",
                           yaxis_title="€"
                        )        


        ### FORECASTING COMPARATIVA
        
        #Primero accedemos a la información del excel. Este contiene tanto los datos de forecast como reales de 15 días.
        df_comparativa_forecast = pd.read_excel('comparativa_forecast.xlsx')
        #Gráfico interactivo

        df_comparativa_forecast = df_comparativa_forecast.set_index('date')    
    
        fig_comparativa = go.Figure()

        #Datos del forecast KWh
        fig_comparativa.add_trace(go.Scatter(
                          x=df_comparativa_forecast.index,
                          y=df_comparativa_forecast['kw_inverter'],
                          mode="lines+markers",
                          line=dict(color='#4B8A8A'),  #, dash='dashdot'
                          marker=dict(size=4, color='#1F354F', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#1F354F")),
                          name="Forecast",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(143, 186, 235, 0.1)'  # Color azul semitransparente
                        ))


        #Datos reales de KWh
        fig_comparativa.add_trace(go.Scatter(
                                 x=df_comparativa_forecast.index, 
                                 y=df_comparativa_forecast["kw_inverter_real"],
                                 mode="lines+markers",
                                 line=dict(width=1, color='#808080'),
                                 marker=dict(size=4, color='#808080', symbol='circle'),
                                 hoverlabel=dict(font=dict(color="#808080")),
                                 fill='tozeroy',  # Rellena el área bajo la curva
                                 name="Reality",
                                 fillcolor='rgba(220, 220, 220, 0.1)',  # Gris muy claro y semitransparente
                                 
                                ))



        # Actualizar las etiquetas de los puntos
        fig_comparativa.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>KWh</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )


        # Configurar las opciones de zoom y desplazamiento
        fig_comparativa.update_layout(xaxis=dict(rangeslider=dict(visible=True)), xaxis_title="Date", yaxis_title="KWh", height=500,             margin=dict(b=30, t=30 ))  # Margen inferior y superior respectivamente

        ###
        
        ###        
        
        ## Gráfico de superficie datos reales de kwh
        #Creamos nuevas variables

        df_comparativa_forecast['hour'] = df_comparativa_forecast.index.hour
        df_comparativa_forecast['fecha'] = df_comparativa_forecast.index.date
        df_comparativa_forecast = df_comparativa_forecast.iloc[:-1]  # Elimina el último registro
        
        fechas_unicas = df_comparativa_forecast.fecha.unique()

        # Crear la lista de horas de 0 a 23
        horas = list(range(24))
        
        # Ajustar el rango del eje x para incluir la hora 23
        rango_x = [0, 23]

        # Crear la cuadrícula de coordenadas x e y
        x, y = np.meshgrid(horas, fechas_unicas)

        # Obtener los valores de kwh correspondientes a las coordenadas x e y
        z = []
        for fecha in fechas_unicas:
            filtro = df_comparativa_forecast['fecha'] == fecha
            valores_kwh = df_comparativa_forecast.loc[filtro, 'kw_inverter_real'].tolist()
            
            # Agregar un valor predeterminado si no hay datos para la hora 23 en esa fecha
            if 23 not in df_comparativa_forecast.loc[filtro, 'hour']:
                valores_kwh.append(0)
                
            z.append(valores_kwh)
        
        
        # Definir el esquema de colores personalizado en base a Viridis, haciendo cambios
        color_personalizado_colorscale = [
            [0, 'rgb(0, 0, 0)'],        # Color negro (en formato RGB)
            [0.1, 'rgb(68, 1, 84)'],
            [0.2, 'rgb(72, 29, 119)'],
            [0.3, 'rgb(68, 55, 149)'],
            [0.4, 'rgb(56, 81, 163)'],
            [0.5, 'rgb(42, 107, 168)'],
            [0.6, 'rgb(30, 132, 171)'],
            [0.7, 'rgb(33, 158, 161)'],
            [0.8, 'rgb(78, 183, 135)'],
            [0.9, 'rgb(146, 205, 94)'],
            [0.95, 'rgb(209, 231, 66)'],
            [1.0, 'rgb(255, 255, 0)']     # Color amarillo (RGB: 255, 255, 0)
        ]
        
        # Crear el gráfico de superficie
        superficie = go.Surface(
            x=x,
            y=y,
            z=z,
            colorscale= color_personalizado_colorscale     
        )

        # Configurar el diseño del gráfico
        layout = go.Layout(
            scene=dict(
                xaxis=dict(title='Hour', autorange='reversed', range=rango_x),  
                yaxis=dict(title='Date', range=[fechas_unicas[0], fechas_unicas[-1]]),
                zaxis=dict(title='Real kWh')
            ),
            
            height=500,  # Ajustar la altura del gráfico
            
            margin=dict(
                b=30,  # Margen inferior
                t=30   # Margen superior
            )
        )

        # Crear la figura y agregar la superficie
        fig_superficie_real = go.Figure(data=[superficie], layout=layout)
        
        # Actualizar las etiquetas de los puntos
        fig_superficie_real.update_traces(
            hovertemplate='<b>Hour</b>: %{x}<br><b>Date</b>: %{y}<br><b>KWh</b>: %{z}<extra></extra>',  # Formato de las etiquetas en el popup
        )
        
        ###
        
        
        ###
        
        ## Gráfico de superficie datos predichos de kwh
        
         # Obtener los valores de kwh correspondientes a las coordenadas x e y
        z = []
        for fecha in fechas_unicas:
            filtro = df_comparativa_forecast['fecha'] == fecha
            valores_kwh = df_comparativa_forecast.loc[filtro, 'kw_inverter'].tolist()
            
            # Agregar un valor predeterminado si no hay datos para la hora 23 en esa fecha
            if 23 not in df_comparativa_forecast.loc[filtro, 'hour']:
                valores_kwh.append(0)
                
            z.append(valores_kwh)

        # Crear el gráfico de superficie
        superficie = go.Surface(
            x=x,
            y=y,
            z=z,
            colorscale= color_personalizado_colorscale  # Esquema de colores personalizado
        )

        # Configurar el diseño del gráfico
        layout = go.Layout(
             scene=dict(
                xaxis=dict(title='Hour' ,autorange='reversed', range=rango_x),
                yaxis=dict(title='Date'),
                zaxis=dict(title='Predicted kWh')
            ),
    
            height=500,  # Ajustar la altura del gráfico
            
            margin=dict(
                b=30,  # Margen inferior
                t=30   # Margen superior
           )
            
        )

        # Crear la figura y agregar la superficie
        fig_superficie_forecast = go.Figure(data=[superficie], layout=layout)

        # Actualizar las etiquetas de los puntos
        fig_superficie_forecast.update_traces(
            hovertemplate='<b>Hour</b>: %{x}<br><b>Date</b>: %{y}<br><b>KWh</b>: %{z}<extra></extra>',  # Formato de las etiquetas en el popup
        )
            
    
        ###
        
        ###      
        
        
        ### Predicción a 7 días vista de la lluvia y nubes para procesos de limpieza

        df_forecasting_7_dias = conexion_open_meteo(fecha_hora_actual)
        
        # Crear la figura
        fig_lluvia_7_dias = go.Figure()

        # Forecasting lluvia 7 días (primera serie de datos)
        fig_lluvia_7_dias.add_trace(go.Scatter(
            x=df_forecasting_7_dias.date,
            y=df_forecasting_7_dias['precipitation_probability'],
            mode="lines+markers",
            line=dict(color='#000080', dash='dashdot'),  # Azul muy oscuro con una línea de puntos y guiones
            marker=dict(size=4, color='#000080', symbol='circle'),  # Azul muy oscuro con marcadores circulares
            hoverlabel=dict(font=dict(color="#000080")),
            name="% Rain",
            fill='tozeroy',
            fillcolor='rgba(0, 0, 128, 0.1)'  # Azul oscuro con una opacidad del 10%
        ))
        
        # Establecer un formato de etiqueta personalizado para la primera serie de datos
        fig_lluvia_7_dias.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>% Rain</b>: %{y}<extra></extra>',  # Etiqueta personalizada
        )

        # Agregar la segunda serie de datos en el mismo gráfico
        fig_lluvia_7_dias.add_trace(go.Scatter(
            x=df_forecasting_7_dias.date,
            y=df_forecasting_7_dias['cloudcover'], 
            mode="lines+markers",
            line=dict(color='#808080', dash='dashdot'),
            marker=dict(size=4, color='#555555', symbol='circle'),
            hoverlabel=dict(font=dict(color="#555555")),
            name="% Cloudiness",  # Cambia el nombre según corresponda
            fill='tozeroy',
            fillcolor='rgba(220, 220, 220, 0.1)',  # Color azul semitransparente
        ))

        # Actualizar las etiquetas de los puntos. Establecer un formato de etiqueta personalizado para la segunda serie de datos
        fig_lluvia_7_dias.update_traces(
            selector=dict(name="% Cloudiness"),
            hovertemplate='<b>Date</b>: %{x}<br><b>% Cloudiness</b>: %{y}<extra></extra>',  # Etiqueta personalizada
        )

        fig_lluvia_7_dias.update_layout(
            #title='Forecast de probabilidad de lluvia',
            xaxis_title="Date",
            yaxis_title="%"
        )
        
        
        
        ###
        
        ###      
                

        ##Forecasting temperatura
        fig1 = go.Figure()

        fig1.add_trace(go.Scatter(
                          x=df_forecast.index,
                          y=df_forecast['temp'],
                          mode="lines+markers",
                          line=dict(color='#FF5555', dash='dashdot'),
                          marker=dict(size=4, color='#FF0000', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#FF0000")),
                          name="Temperature",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(255, 204, 204, 0.1)'  # Color rojo semitransparente
                        ))
       
        # Actualizar las etiquetas de los puntos
        fig1.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>T[ºC]</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )
        
        fig1.update_layout(
                           #title='Forecast of energy production',
                           xaxis_title="Date",
                           yaxis_title="ºC"
                        )        

        ##Forecasting humidity
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
                          x=df_forecast.index,
                          y=df_forecast['humidity'],
                          mode="lines+markers",
                          line=dict(color='#4B8A8A', dash='dashdot'),  #1F354F
                          marker=dict(size=4, color='#1F354F', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#1F354F")),
                          name="Humidity",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(143, 186, 235, 0.05)'  # Color azul semitransparente
                        ))
        # Actualizar las etiquetas de los puntos
        fig2.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>%</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )

        fig2.update_layout(
                           #title='Forecast of energy production',
                           xaxis_title="Date",
                           yaxis_title="%"
                        )




        ##Forecasting velocidad del viento
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
                          x=df_forecast.index,
                          y=df_forecast['wind_speed'],
                          mode="lines+markers",
                          line=dict(color='#C0C0C0', dash='dashdot'),  
                          marker=dict(size=4, color='#888888', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#555555")),
                          name="Wind speed",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(255, 255, 255, 0.3)'  # Color blanco semitransparente
                        ))
        # Actualizar las etiquetas de los puntos
        fig3.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>Km/h</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )

        fig3.update_layout(
                           #title='Forecast of energy production',
                           xaxis_title="Date",
                           yaxis_title="Km/h"
                        )


        ##Forecasting del porcentaje de nubes
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
                          x=df_forecast.index,
                          y=df_forecast['clouds'],
                          mode="lines+markers",
                          line=dict(color='#808080', dash='dashdot'),
                          marker=dict(size=4, color='#555555', symbol='circle'),
                          hoverlabel=dict(font=dict(color="#555555")),
                          name="Cloudiness",
                          fill='tozeroy',  # Rellena el área bajo la curva
                          fillcolor='rgba(220, 220, 220, 0.1)',  # Color azul semitransparente
                        ))
        # Actualizar las etiquetas de los puntos
        fig4.update_traces(
            hovertemplate='<b>Date</b>: %{x}<br><b>%</b>: %{y}<extra></extra>',  # Formato de las etiquetas en el popup
        )

        fig4.update_layout(
                           #title='Forecast of energy production',
                           xaxis_title="Date",
                           yaxis_title="%"
                        )  

        ###Iconos del tiempo
        #Sacamos la moda de weather_icon: el valor que más se repite
        moda_weather_icon = statistics.mode(df_forecast['weather_icon'])     
        moda_actualizada = moda_weather_icon[0:2] + 'd'   #Actualizamos para que siempre salga el icono de día

        #Sacamos la moda de weather_description: el valor que más se repite
        moda_weather_description = statistics.mode(df_forecast['weather_description'])     



        #Actualizamos los códigos con el nombre del archivo json
        if moda_actualizada == '01d':
            lottie_name = "sun"

        elif moda_actualizada == '02d':
            lottie_name = "cloud_sun"

        elif (moda_actualizada == '03d') | (moda_actualizada == '04d'):
            lottie_name = "cloud"
            
        elif (moda_actualizada == '09d') | (moda_actualizada == '10d'):
            lottie_name = "rain"

        elif moda_actualizada == '11d':
            lottie_name = "cloud_with_thunder"    

        elif moda_actualizada == '13d':
            lottie_name = "snow"  
            
        def cargar_lottie(filepath:str):
            with open(filepath, "r") as f:
                return json.load(f)





        # OUTPUT

        st.header('Field information' ,anchor=None)
        col1,col2 =st.columns((1.5,1))

        with col1:

            @st.cache_resource()
            def create_map():

                fig_folium = Figure()

                m = folium.Map(location=[38.6628444, -5.391886111111112], zoom_start=13)

                fig_folium.add_child(m)

                folium.TileLayer('Stamen Terrain', name='Terrain map').add_to(m)

                folium.Marker([38.6628444, -5.391886111111112], popup="Solar field location", tooltip="Solar field location", icon=folium.Icon(color="green", icon="map-marker")).add_to(m)

                folium.LayerControl().add_to(m)

                return(m)

            # Crear el mapa
            mapa = create_map()

            #Visualizar mapa  
            st_data = folium_static(mapa, width=450, height = 250) 



        with col2.container():

            col2.metric("Location", 'Helechal (ES)')
            col2.metric("No. of solar panels", 7392)    
            col2.metric("Plant area fenced", " 25858 m\u00b2", )




        ### Forecast de energía

        # Primero dejamos un espacio en blanco
        espacio = st.empty()
        espacio.markdown("---")

        #Añadimos subheader
        st.header('Forecast of energy production',anchor=None)

        #Creamos nuevas columnas
        col3,col4 = st.columns((4.5,1))    

        # Mostrar el gráfico interactivo en Streamlit
        col3.plotly_chart(fig, use_container_width=True)


        with col4.container():
            st.markdown('<div style="height: 125px;"></div>', unsafe_allow_html=True)

            col4.metric("Predicted energy produced", str(round(MWh_forecasting,2)) + " MWh")

            #Utilizamos la función color_de_texto creada antes para cambiar el color de la métrica
            color_de_texto('Predicted energy produced', wch_title_colour="#228B22", wch_value_colour="#228B22")

            #col4.metric("Evaluation metric", " R\u00b2 : 0.92")

            
        ### Comparativa datos forecast vs realidad
        
        with st.expander("**Forecasting accuracy**"):
            
            st.subheader("Comparison: Forecast vs Reality for past data over a 14 days period")
            # Mostrar el gráfico interactivo en Streamlit

            tab1, tab2, tab3  = st.tabs(["Production comparison", "Real production", "Predicted production"])

            tab1.subheader("Production comparison")
            tab1.plotly_chart(fig_comparativa, use_container_width=True)

            tab2.subheader("Real production")
            tab2.plotly_chart(fig_superficie_real, use_container_width=True)

            tab3.subheader("Predicted production")
            tab3.plotly_chart(fig_superficie_forecast, use_container_width=True)            
            
        # Dejamos un espacio en blanco
        espacio = st.empty()
        espacio.markdown("---")
        
        
        ### Precio energía
        #Añadimos subheader
        st.header('Selling price of energy',anchor=None)

        st.caption('Price of KWh is provided by the website _https://www.omie.es/es/market-results/daily/daily-market/daily-hourly-price_. This is the platform that provides real-time information on prices and operations in the electricity markets of the Iberian Peninsula in Spain and Portugal.')
        
        #Creamos nuevas columnas
        col3,col4 = st.columns((4.5,1))        
        
        col3.plotly_chart(fig_precio, use_container_width=True)
                
        with col4.container():
            st.markdown('<div style="height: 125px;"></div>', unsafe_allow_html=True)

            col4.metric("Estimated income", str(round(euros_total,2)) + " €")

            #Utilizamos la función color_de_texto creada antes para cambiar el color de la métrica
            color_de_texto('Estimated income', wch_title_colour="#228B22", wch_value_colour="#228B22")

            
        # Dejamos un espacio en blanco
        espacio = st.empty()
        espacio.markdown("---")
        
        
            
            
        ### Limpieza
        
        st.header('Clean-up measures',anchor=None)
                
        ### Aviso del sensor de polvo
        
        #Dejar un espacio entre el título y el botón
        st.markdown('<div style="height: 17px; margin-left: 15px;"></div>', unsafe_allow_html=True)
        
        # Definir el estilo personalizado
        fondo_anaranjado = """
        <style>
            .fondo_naranja {
                background-color: rgba(255, 240, 210, 0.7);
                padding: 20px;
                border-radius: 5px;
            }
        </style>
        """

        fondo_azulado = """
        <style>
            .fondo_azul {
                background-color: rgba(200, 210, 230, 0.4);
                padding: 20px;
                border-radius: 5px;
            }
        </style>
        """
        
        # Dejar espacio entre emoji y texto
        espacio = """
        <style>
        .space {
            margin-right: 10px;
        }
        </style>
        """
        
        
        ## Mensaje se detectan fallos de conexión en el sensor de energía
        # Verificar si la columna contiene el valor '-'
        if '-' in df_historico['kw_inverter'].values:
            st.markdown(espacio, unsafe_allow_html=True)
            st.markdown('<div class="fondo_naranja"> ⚠️ <span class="space"></span> A loss of connection is detected concerning the data collected by the power sensor. This may lead to worse model predictions.</div>', unsafe_allow_html=True)
            st.markdown(fondo_anaranjado, unsafe_allow_html=True)
     
        # Mensaje de sensor de polvo
        
        #Primero hacemos un pretratamiento por si los datos vinieran como '-'
        df_historico_indicador = df_historico[(df_historico['loss_sensor_1'] != '-') & (df_historico['loss_sensor_2'] != '-')]
        
        if (df_historico_indicador.loss_sensor_1.mean() > 0.94 ) & (df_historico_indicador.loss_sensor_2.mean() > 0.99):
            # Agregar el estilo personalizado
            st.markdown(espacio, unsafe_allow_html=True)
            st.markdown('<div class="fondo_naranja"> ⚠️ <span class="space"></span> A high dust amount is detected by the sensors. It is recommended to follow up for cleaning if the amount of dust does not decrease.</div>', unsafe_allow_html=True)
            st.markdown(fondo_anaranjado, unsafe_allow_html=True)
            
        else:
            # Agregar el estilo personalizado
            st.markdown(espacio, unsafe_allow_html=True)
            st.markdown('<div class="fondo_azul"> ℹ️ <span class="space"></span> Sensors detect normal accumulation of dust; therefore, no cleaning measures are required yet.</div>', unsafe_allow_html=True)
            st.markdown(fondo_azulado, unsafe_allow_html=True)   

        #Añadimos subtítulo para el gráfico    
        st.subheader('Rain and cloud forecast for upcoming 7 days')
        
        #Comentarios
        st.caption('Rain and cloud forecast is provided by the website _https://open-meteo.com/en/docs_.')
        st.caption('In case you require cleaning measures to be carried out in the solar field, please refer to the following 7-day forecast chart to find the optimal time for cleaning.')
        
        # Gráfico de previsión de lluvia y nubosidad 7 días vista
        st.plotly_chart(fig_lluvia_7_dias, use_container_width=True)
       
        ### Forecast del tiempo

        #Dejar un espacio entre el mensaje y la línea de separación
        st.markdown('<div style="height: 17px; margin-left: 15px;"></div>', unsafe_allow_html=True)
       
        # Primero dejamos un espacio en blanco
        espacio = st.empty()
        espacio.markdown("---")

        #Cargamos icono de lottie
        lottie_icon = cargar_lottie(f"{lottie_name}.json")


        st.header('Weather forecast for the upcoming 24 hours')
        
        st.caption('Weather forecast is provided by the website _https://openweathermap.org/_.')

        col5,col6 = st.columns((1.65,1))

        with col5:

            tab1, tab2, tab3, tab4 = st.tabs(["🌡️ Temperature", "💧 Humidity", "💨 Wind speed", "☁️ Cloudiness"])

            tab1.subheader("Temperature")
            tab1.plotly_chart(fig1, use_container_width=True)

            tab2.subheader("% Humidity")
            tab2.plotly_chart(fig2, use_container_width=True)

            tab3.subheader("Wind speed")
            tab3.plotly_chart(fig3, use_container_width=True)

            tab4.subheader("% Cloudiness")
            tab4.caption('Weather forecast for this parameter may vary from the data shown in the "Clean-up measures" section. This is because the information comes from different sources.')
            tab4.plotly_chart(fig4, use_container_width=True)


        #Mostrar lottie animación
        
        
        with col6:
            
            col7,col8 = st.columns((1,7))
            
            with col7:
                st.empty()
                
            with col8:

                st.markdown('<div style="height: 60px; margin-left: 15px;"></div>', unsafe_allow_html=True)
                st.metric("Main weather", moda_weather_description.title())  #Escribirá en mayúsculas el principio de cada letra
                st_lottie(
                        lottie_icon,
                        speed = 1.1,
                        loop = True,
                        quality = "high",
                        height = 150,  
                        width = 150  
                        )  


            col9,col10 = st.columns(2)
            
            with col9:
                st.metric("Max. Temp.", str(round(df_forecast.temp.max(),1)) + (" ºC"))
                st.metric("Max. % Humidity", str(df_forecast.humidity.max()) + (" %"))

            with col10:
                st.metric("Max. Wind Speed", str(round(df_forecast.wind_speed.max(),1)) + (" Km/h"))
                st.metric("Max. % Cloudiness", str(df_forecast.clouds.max()) + (" %"))
        
        
        
                
        ### Descarga de excel

        # Primero dejamos un espacio en blanco
        espacio = st.empty()
        espacio.markdown("---")
                
        st.header('Export data')
        
        
        # Agregar el botón de descarga
        
        def download_excel(df, df_forecasting_7_dias):
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            
            #Reseteamos índice
            df = df.reset_index()
            
            
            #Juntamos con dataframe del precio para obtener el precio por horas
            
            df = pd.merge(df, df_final_omie[['date','€_KWh','€']], how = 'left', on = 'date')           
            
            #Cambiamos el formato de la columna date para que sea el que queremos par
            df['date'] = df['date'].dt.strftime('%d.%m.%Y %H:%M')
            df_forecasting_7_dias['date'] = df_forecasting_7_dias['date'].dt.strftime('%d.%m.%Y %H:%M')
            
            #Indexamos filas de interés
            df = df[['date','kw_inverter','€_KWh','€','temp','humidity','wind_speed','wind_deg','clouds','weather_main', 'weather_description']]
            
            # Renombrar las columnas en una sola línea de código
            df = df.rename(columns={'date': 'Date', 'kw_inverter': 'KWh', 'temp': 'Temperature [ºC]', 'humidity': '% Humidity', 'wind_speed': 'Wind speed [Km/h]', 'wind_deg': 'Wind degrees', 'clouds': '% Cloudiness', 'weather_main': 'Weather type', 'weather_description': 'Weather description'})
            df_forecasting_7_dias = df_forecasting_7_dias.rename(columns = {'date': 'Date', 'precipitation_probability': '% Rain', 'cloudcover': '% Cloudiness'})

            df.to_excel(writer, sheet_name='Forecasting', index = False)
            df_forecasting_7_dias.to_excel(writer, sheet_name='Weather forecast for 7 days', index=False)

            workbook = writer.book   #Objeto workbook

            worksheet = writer.sheets['Forecasting']
            worksheet_1 = writer.sheets['Weather forecast for 7 days']

            # Ajustar el tamaño de las columnas
            for column in range(df.shape[1]):
                column_width = max(df.iloc[:, column].astype(str).map(len).max(), len(df.columns[column]))
                worksheet.set_column(column, column, column_width + 4)
            
            for column in range(df_forecasting_7_dias.shape[1]):
                column_width = max(df_forecasting_7_dias.iloc[:, column].astype(str).map(len).max(), len(df_forecasting_7_dias.columns[column]))
                worksheet_1.set_column(column, column, column_width + 4)            

            # Aplicar formato de color de relleno a la segunda columna
            color_gris = workbook.add_format({'bold': True, 'bg_color': '#C0C0C0', 'align': 'center'})  # Color de relleno gris muy claro, negrita y centrado
            color_gris_claro = workbook.add_format({'bg_color': '#F0F0F0'})  # Color de relleno gris plateado claro

            worksheet.conditional_format(1, 1, df.shape[0], 1, {'type': 'no_blanks', 'format': color_gris_claro})  # Aplicar formato a la segunda columna

            worksheet.write(0, 1, df.columns[1], color_gris)  # Aplicar formato al nombre de la columna 2

            writer.save()
            output.seek(0)
            return output
        
        # Generar el enlace de descarga
        output = download_excel(df_forecast, df_forecasting_7_dias)

        b64 = base64.b64encode(output.read()).decode()
        
        # Personalizamos el botón de descarga
        boton = f'''
            <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="forecast_data.xlsx">
                <button style="background-color: rgba(34, 139, 34, 0.8); color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; border: 2px solid #1F354F;">
                    Download forecast
                </button>
            </a>
        '''
        #background-color: #228B22
        
        
        #Dejar un espacio entre el título y el botón
        st.markdown('<div style="height: 17px; margin-left: 15px;"></div>', unsafe_allow_html=True)
        
        # Mostrar el botón de descarga personalizado
        st.markdown(boton, unsafe_allow_html=True)


        
        
        
        ### Información adicional
        
        # Primero dejamos un espacio en blanco
        espacio = st.empty()
        espacio.markdown("---")
        
        st.header('Information about the project and contact')    
        st.markdown('<div style="height: 20px; ></div>', unsafe_allow_html=True)    
        
        with st.expander("**Further information**"):
             

            st.markdown('<div style="height: 40px; "></div>', unsafe_allow_html=True)
            
            #st.subheader("Information about the project")
                
                
            st.markdown('This application has been developed as part of my final degree project in Industrial Technologies Engineering at Rey Juan Carlos University. The main objective is to address a problem in the field of engineering.')

            st.markdown('The application, designed in Streamlit, is the result of extensive research and development carried out as part of my thesis. The main focus has been to develop a 24 hour energy forecasting model  for a solar field belonging to a company specialised in photovoltaic solar energy.')

            st.markdown('In order to obtain accurate predictions, methodologies such as data analysis and development of a machine learning model have been implemented.')
                
            st.markdown('The result is an application that is easy and simple to use that allows users to import historical data from a solar plant from the previous 24 hours and obtain the solar energy production forecast for the next 24 hours. In addition, the connection to a weather forecasting application is established in order to improve the results of the prediction.')
                
            st.markdown('This work represents a significant contribution to the field of the solar energy industry. The developed forecasting model has the potential to optimise the management and planning of power generation in solar fields, helping the company to maximise its operational efficiency and reduce costs. By predicting energy production, hours in advance, supply decisions can be made in relation to demand, ensuring a more stable supply of energy.')
                
            st.markdown('I am grateful to both my university and tutor fo giving me the chance to carry out this final thesis. I would also like to express my gratitude to the company that collaborated and provided the necessary data for the development of the prediction model.')
            
            st.markdown('For further information, please contact: ')
                
            # Añadimos logo linkedin

            embed_component= {'linkedin':"""<script src="https://platform.linkedin.com/badges/js/profile.js" async defer type="text/javascript"></script>
            <div class="badge-base LI-profile-badge" data-locale="es_ES" data-size="medium" data-theme="light" data-type="VERTICAL" data-vanity="marina-vendrell-pons-46a7a5245" data-version="v1"></div>

                  """}

            #components.html(embed_component['linkedin'], height=250) #, width=300, height=150
            st.components.v1.html(embed_component['linkedin'], height=250)   
                
                
else:
    
    #Calculamos la fecha y hora actuales y 24h previas para mostrar mensaje. Esta será la hora de Madrid, España
    
    def obtener_fecha_hora_madrid():
        zona_horaria_madrid = pytz.timezone('Europe/Madrid')
        fecha_hora_madrid = datetime.now(zona_horaria_madrid)
        return fecha_hora_madrid.replace(minute=0, second=0, microsecond=0)
    
    # Obtener la fecha y hora de Madrid
    fecha_hora_actual = obtener_fecha_hora_madrid()
    
    # 23 horas antes
    desplazamiento = timedelta(hours=23)
    fecha_24_horas_antes = fecha_hora_actual - desplazamiento
    

    #Texto a mostrar
    st.write('This is an application to **predict the production of energy of a solar field 24 hours in advance**. It is easy and simple to use and allows users to import historical data from a solar field from the previous 24 hours and obtain the solar energy production forecast for the next 24 hours.')
    st.write('It has the potential to optimise the management and planning of power generation in solar fields, helping the company to maximise its operational efficiency and reduce costs.')
    st.write('The application contains an artificial intelligence model designed exclusively for the **Helechal solar field (ES)**.  Therefore, the information uploaded and the predictions will be made only for this field.')
    st.write(f"To proceed, please upload the files in the left sidebar. These must contain the solar field information detailed from **{fecha_24_horas_antes.strftime('%d-%m-%Y at %Hh')}** to **{fecha_hora_actual.strftime('%d-%m-%Y at %Hh')}**, all period included otherwise the application will not work.")
    st.write('The variables required by the user to run the model are the following:')
    st.markdown("<b><em>Irradiation_average</b></em>, <b><em>Power by Inverter</b></em>, <b><em>Ambient Temperature</b></em>, <b><em>Module Temperature</b></em>, <b><em>Soiling Loss Sensor 1</b></em> and <b><em>Soiling Loss Sensor 2</b></em> ", unsafe_allow_html=True)
    
    st.write('* Please note that due to the fact that this is a demo application, weather data is accessed via a free account. The forecast can only be calculated approximately 40 times per day. If access is required more than this, the account will be blocked and the application will not work. In the future, a premium account will probably be created to avoid this effect.')

    
    #parrafos = [ "Irradiation_average", "Power by Inverter",  "Ambient Temperature", "Module Temperature", "Soiling Loss Sensor 1", "Soiling Loss Sensor 2"]

    # Mostrar los párrafos con puntos al principio
    #for i, parrafo in enumerate(parrafos):
        #st.write(f"{i + 1}. {parrafo}")
       # indentacion = "&nbsp;" * 4
       # contenido = f"{indentacion}{i + 1}. <b>{parrafo}</b>"
       # st.markdown(f"<p style='text-indent: 20px;'>{contenido}</p>", unsafe_allow_html=True)
        
    

























