#!/usr/bin/python
#coding: utf-8

import xml.etree.ElementTree as ET
import urllib
import csv
import math
import sys
import unicodedata
import HTMLParser
import codecs
import time

# llegeix el fitxer .csb i crea una llista amb totes les estacions de bus
def creaLlistaEstBus ():
	llEstBus = []
	fitxerBusos = open('ESTACIONS_BUS.csv', 'rb')
	readerBusos = csv.DictReader(fitxerBusos, delimiter=';', quotechar=' ')
	for row in readerBusos:
		llEstBus.append(row)
	fitxerBusos.close()
	return llEstBus

# llegeix el fitxer .csb i crea una llista amb totes les estacions de tren i metro
def creaLlistaEstTren ():
	llEstTren = []
	fitxerTren = open('TRANSPORTS.csv', 'rb')
	readerTren = csv.DictReader(fitxerTren, delimiter=';', quotechar=' ')
	for row in readerTren:
		llEstTren.append(row)
	fitxerTren.close()
	return llEstTren

# donada la coordenada (lat1, lon1) i la coordenada (lat2, lon2)
# calcula la distancia entre elles
def distancia (lat1, lon1, lat2, lon2):
	lat1 = lat1 * math.pi / 180
	lon1 = lon1 * math.pi / 180
	lat2 = lat2 * math.pi / 180
	lon2 = lon2 * math.pi / 180
	dist = 6378.137 * math.acos(math.cos(lat1) * math.cos(lat2) * 
		math.cos(lon2 - lon1) + math.sin(lat1) * math.sin(lat2))
	return dist

def unicode_csv_reader (utf8_data, dialect=csv.excel, **kwargs):
    csv_reader = csv.reader(utf8_data, dialect=dialect, **kwargs)
    for row in csv_reader:
        yield [unicode(cell, 'utf-8') for cell in row]

# lat i lon son les coordenades de l'esdeveniment
# rBici es la root del xml on apareixen les estacions de bici
# retorna dues llistes, una amb les estacions que tenen bicis disponibles
# i a menys de 500m i una altra amb les estacions que tenen slots buits i
# estan a menys de 500m
def buscaEstacionsBicing (lat, lon, rBici):
	llSlots = []
	llBicis = []
	for station in rBici.iter("station"):
		lat2 = float(station.find("lat").text)
		lon2 = float(station.find("long").text)
		dist = distancia(lat, lon, lat2, lon2)
		if (dist <= 0.5):
			if int(station.find("slots").text) > 0:
				llSlots.append(station)
			if int(station.find("bikes").text) > 0:
				llBicis.append(station)
	llSlots.sort(key=lambda x : distancia(lat, lon, float(x.find("lat").text), float(x.find("long").text)))
	llBicis.sort(key=lambda x : distancia(lat, lon, float(x.find("lat").text), float(x.find("long").text)))
	return llSlots, llBicis

# lat i lon son les coordenades de l'esdeveniment
# retorna la llista d'estacions de bus que estan a menys
# de 500m de l'esdeveniment, separada per busos diurns
# i busos nocturns
def buscaEstacionsBus (llEstacions, lat, lon):
	llBusDiurn = []
	llBusNocturn = []
	for row in llEstacions:
		lat2 = float(row["LATITUD"])
		lon2 = float(row["LONGITUD"])
		dist = distancia(lat, lon, lat2, lon2)
		if (dist <= 0.5):
			if row["NOM_CAPA_ANG"] == "Day buses":
				llBusDiurn.append(row)
			else:
				llBusNocturn.append(row)
	llBusDiurn.sort(key=lambda x : distancia(lat, lon, float(x["LATITUD"]), float(x["LONGITUD"])))
	llBusNocturn.sort(key=lambda x : distancia(lat, lon, float(x["LATITUD"]), float(x["LONGITUD"])))
	return llBusDiurn, llBusNocturn


# lat i lon son les coordenades de l'esdeveniment
# retorna la llista d'estacions de tren que estan a menys
# de 500m de l'esdeveniment
def buscaEstacionsTren (llEstacions, lat, lon):
	llTrens = []
	for row in llEstacions:
		lat2 = float(row["LATITUD"])
		lon2 = float(row["LONGITUD"])
		dist = distancia(lat, lon, lat2, lon2)
		if (dist <= 0.5):
			llTrens.append(row)
	llTrens.sort(key=lambda x : distancia(lat, lon, float(x["LATITUD"]), float(x["LONGITUD"])))
	return llTrens

# elimina els accents a la paraula passada com a parametre s
def elimina_tildes(s):
	if type(s) == str:
		s = unicode(s, "utf-8")
	return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

# comprova si una activitat satisfa la condicio que li passa
# l'usuari al programa com a parametre d'entrada
def satisfaCond (info, cond):
	cond = eval(cond)
	# si es una conjuncio
	if isinstance(cond, tuple): 
		for elem in cond:
			if isinstance(elem, str):
				if not elem in info:
					return False
			elif not satisfaCond(info, elem):
				return False
		return True

	# si es una disjuncio
	elif isinstance(cond, list): 
		for elem in cond:
			if isinstance(elem, str):
				if elem in info:
					return True
			elif satisfaCond(info, elem):
				return True
		return False

	# si es un unic string
	else:
		return cond in info

# obte la llista d'activitats que satisfan la condicio
# que l'usuari introdueix
def buscaActivitats (rAct):
	llActes = []
	paramsLower = elimina_tildes(sys.argv[1].lower())
	for acte in rAct.iter("acte"):
		info = acte.find("nom").text + " " + acte.find("lloc_simple/nom").text + \
			" " + acte.find("lloc_simple/adreca_simple/barri").text
		info = elimina_tildes(info.lower()).replace("'"," ").split(" ")
		if satisfaCond(info, paramsLower):
			llActes.append(acte)
	return llActes

# identifica quin transport fara servir l'usuari, en funcio de les preferencies
# d'aquest i la diponibilitat dels transports
def buscaTipusTransport(llTipusTrans, llTrans, llBicis):
	tipusTrans = "peu"
	for t in llTipusTrans:
		if t == "transport" and len(llTrans) > 0:
			tipusTrans = t
			break
		elif t == "bicing" and len(llBicis) > 0:
			tipusTrans = t
			break
		elif t == "peu":
			break
	return tipusTrans

# obte les linies que conflueixen en una parada en forma d'un set
def obteLinies(parada):
	linies = parada.split(" ")[1].split("(")[0].split(")")[0].split("-")
	setLinies = set()
	setLinies.update(linies)
	return setLinies

def convertUnicode (lletra):
	try:
		return u"" + lletra
	except UnicodeDecodeError:
		return "*"

def escriuTransport(llTrans, htmlFile, lat, lon):
	llLinies = obteLinies(llTrans[0]["EQUIPAMENT"])
	if len(llTrans) > 1:
		llLinies.update(obteLinies(llTrans[1]["EQUIPAMENT"]))
	if len(llTrans) > 2:
		llLinies.update(obteLinies(llTrans[2]["EQUIPAMENT"]))

	llAux = llTrens[1:] + llBusDiurn[1:] + llBusNocturn[1:]
	llAux.sort(key=lambda x : distancia(lat, lon, float(x["LATITUD"]), float(x["LONGITUD"])))
	for trans in llAux:
		linia = set(obteLinies(trans["EQUIPAMENT"]))
		# evita que posi una parada on totes les seves linies ja son accessibles
		# a traves de les parades implicites a llTrans
		if not linia.issubset(llLinies):
			llLinies.update(linia)
			llTrans.append(trans)
			if len(llTrans) == 6:
				break
	llTrans.sort(key=lambda x : distancia(lat, lon, float(x["LATITUD"]), float(x["LONGITUD"])))
	rowspan = len(llTrans) + 1
	escriuInfoActivitat(activitat, rowspan)
	htmlFile.write(u'<td rowspan="' + str(rowspan) + '">Transport public</td>')

	for trans in llTrans:
		htmlFile.write(u"<tr>")
		paraula = ""
		for i in trans["EQUIPAMENT"]:
			paraula += convertUnicode(i)
		htmlFile.write(u"<td>" + paraula + "</td>")

		dist = distancia(lat, lon, float(trans["LATITUD"]), float(trans["LONGITUD"]))
		htmlFile.write(u"<td>" + str(int(dist*1000)) + "</td>")

		htmlFile.write(u"</tr>")	

# escriu a la taula html les estacions de bicing properes
# a l'activitat
def escriuBicing(htmlFile, llBicis, llSlots, activitat, lat, lon):
	rwspanBicis = len(llBicis[:5]) + 1
	rwspanSlots = len(llSlots[:5]) + 1
	rowspan = rwspanBicis + rwspanSlots + 1
	escriuInfoActivitat(activitat, rowspan)

	htmlFile.write(u"<tr>")
	htmlFile.write(u'<td rowspan="' + str(rwspanBicis) + '"><p>Bicing<p>(bicis disponibles)</td>')

	for bici in llBicis[:5]:
		htmlFile.write(u"<tr>")
		try:
			htmlFile.write(u"<td>" + bici.find("street").text + \
			", " + bici.find("streetNumber").text + "</td>")
		except TypeError:
			htmlFile.write(u"<td>" + bici.find("street").text + "</td>")
		
		lat2 = float(bici.find("lat").text)
		lon2 = float(bici.find("long").text)
		dist = distancia(lat, lon, lat2, lon2)
		htmlFile.write(u"<td>" + str(int(dist*1000)) + "</td>")

		htmlFile.write(u"</tr>")
	htmlFile.write(u"</tr>")

	htmlFile.write(u"<tr>")
	htmlFile.write(u'<td rowspan="' + str(rwspanSlots) + '"><p>Bicing<p>(slots lliures)</td>')

	for bici in llSlots[:5]:
		htmlFile.write(u"<tr>")
		try:
			htmlFile.write(u"<td>" + bici.find("street").text + \
			", " + bici.find("streetNumber").text + "</td>")
		except TypeError:
			htmlFile.write(u"<td>" + bici.find("street").text + "</td>")

		lat2 = float(bici.find("lat").text)
		lon2 = float(bici.find("long").text)
		dist = distancia(lat, lon, lat2, lon2)
		htmlFile.write(u"<td>" + str(int(dist*1000)) + "</td>")

		htmlFile.write(u"</tr>")
	htmlFile.write(u"</tr>")

# escriu la taula per l'activitat en la qual ha d'anar a peu
def escriuPeu(activitat):
	escriuInfoActivitat(activitat, 1)
	htmlFile.write(u"<td>A peu</td>")
	htmlFile.write(u"<td>Amb sabates o descalç</td>")
	htmlFile.write(u"<td>Si camines ràpid se't farà més curt</td>")
	
# escriu la informacio de l'activitat en una taula html
def escriuInfoActivitat (activitat, rowS):
	td = '<td rowspan="' + str(rowS) + '">'
	htmlFile.write(u"" + td + str(numAct) + "</td>")
	htmlFile.write(u"" + td + activitat.find("nom").text + "</td>")
	htmlFile.write(u"" + td + activitat.find("lloc_simple/adreca_simple/carrer").text + ", " + \
		activitat.find("lloc_simple/adreca_simple/numero").text + "</td>")
	htmlFile.write(u"" + td + activitat.find("data/data_proper_acte").text + "</td>")


# obre l'XML dels llocs web que necessitem
# pel bicing
temps1 = time.time()
temps0 = time.time()
f = urllib.urlopen("http://wservice.viabicing.cat/v1/getstations.php?v=1")
tree = ET.parse(f)
rBici = tree.getroot()
# per les activitats que es fan a Barcelona
f = urllib.urlopen("http://w10.bcn.es/APPS/asiasiacache/peticioXmlAsia?id=199")
tree = ET.parse(f)
rAct = tree.getroot()
# estacions de tren
print "Temps lectura xmls:", time.time() - temps1

temps1 = time.time()
llEstTren = creaLlistaEstTren()
llEstBus = creaLlistaEstBus()
print "Temps lectura fitxers:", time.time() - temps1
temps1 = time.time()

# plantilla html on es representara la sortida
plantillaHtml = u"""
<!DOCTYPE html>

<html lang="ca">
	<head>
		<title> Taula activitats </title>
		<meta charset="UTF-8">
	</head>

	<style>
		table, th, td {
		    border: 1px solid black;
		    border-collapse: collapse;
		}
		th, td {
		    padding: 5px;
		}
	</style>
	
	<body> 
		<table>
			<caption>Resultats de la cerca</caption>
			<tr>
				<th colspan="4">Esdeveniment</th>
				<th colspan="3">Transport</th>
			</tr>
			<tr>
				<th> </th>
				<th style="width:25%">Nom</th>
				<th style="width:20%">Adreça</th>
				<th style="width:10%">Data</th>
				<th>Tipus transport</th>
				<th>Opcions</th>
				<th>Distància</th>
			</tr>
"""
totalTrens = 0
totalBusos = 0
totalBicis = 0
tempsEscriure = 0
htmlFile = codecs.open("activitats.html", "w", "utf-8")
htmlFile.write(plantillaHtml)
numAct = 1
for activitat in buscaActivitats(rAct):
	htmlFile.write(u"<tr>")

	# transport (bicing o FCG)
	llTipusTrans = eval(sys.argv[2])
	coord = activitat.find("lloc_simple/adreca_simple/coordenades/googleMaps").attrib
	lat = float(coord["lat"])
	lon = float(coord["lon"])
	temps3 = time.time()
	[llSlots, llBicis] = buscaEstacionsBicing(lat, lon, rBici)
	totalBicis += time.time() - temps3
	
	temps3 = time.time()
	llTrens = buscaEstacionsTren(llEstTren, lat, lon)
	totalTrens += time.time() - temps3

	temps3 = time.time()
	[llBusDiurn, llBusNocturn] = buscaEstacionsBus(llEstBus, lat, lon)
	totalBusos += time.time() - temps3

	llTrans = llTrens[0:1] + llBusDiurn[0:1] + llBusNocturn[0:1]

	# busca quin tipus de transport utilitzara l'usuari
	tipusTrans = buscaTipusTransport(llTipusTrans, llTrans, llSlots + llBicis)

	time4 = time.time()
	if tipusTrans == "transport":
		# mira que escrigui el transport totes les vegades i no nomes la primera
		escriuTransport(llTrans, htmlFile, lat, lon)

	elif tipusTrans == "bicing":
		escriuBicing(htmlFile, llBicis, llSlots, activitat, lat, lon)

	# a peu
	else:
		escriuPeu(activitat)
	tempsEscriure += time.time() - time4

	numAct += 1
	htmlFile.write(u"</tr>")

htmlFile.write(u"</table>")
htmlFile.write(u"</body>")
htmlFile.write(u"</html>")
htmlFile.close()

print "Temps total bicis:", totalBicis
print "Temps total busos", totalBusos
print "Temps total trens", totalTrens
print "Temps escriure", tempsEscriure
print "Temps total:", time.time() - temps0
