from random import randint

banque = int(input("Choisir une mise de départ : "))
mise1 = int(0)
mise2 = int(0)

while banque > 0:
    a = randint(0,36)
    b = int(input("Choisi ton numéro : "))

    if b not in range(0, 36):
        b = int(input("Merci de choisir un chiffre entre 0 et 36 : "))
    elif b in range(0, 36):
        break
    
    miseChiffre = int(input("Choisi un montant pour la mise chiffre : "))
    try:
        assert 0 <= miseChiffre <= banque
        banque = banque - miseChiffre
    except:
        print("Tu n'as pas assez dans ta banque. Il reste :",banque,"€")

    if c not in ["Rouge", "Noir"]:
        c = str(input("Merci de choisir noir ou rouge: "))
    elif c in ["Rouge", "Noir"]:
        break
    Red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    Black = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]

    miseCouleur = int(input("Choisi un montant pour la mise couleur : "))
    try:
        assert 0 <= miseCouleur <= banque
        banque = banque - miseCouleur
    except:
        print("Tu n'as pas assez dans ta banque. Il reste :",banque,"€")

    if a == b:
        mise1 = miseChiffre*36
    elif a != b:
        mise1 = 0

    if (Red.count(a) == True):
        couleur = "Rouge"
    elif (Black.count(a) == True):
        couleur = "Noir"
    elif (a == 0):
        couleur = "0"
        mise2 = miseCouleur/2
    
    if (c == couleur):
        mise2 = miseCouleur*2
    elif (c != couleur):
        mise2 = 0
    
    banque = banque + mise1 + mise2

    print ("Voici ta banque : ", banque, "€")
    print ("Le bon chiffre était :", a)
    print ("La bonne couleur est : ", couleur)