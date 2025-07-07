from random import randint

Range = 1000000

Li = []
for i in range(Range):
    Li.append(randint(0,36))
for i in range(37):
    print ("Nombre de", i, "dans la liste : ", Li.count(i), "Pourcentage : ", Li.count(i)/Range*100,"%")