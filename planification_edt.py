from ortools.sat.python import cp_model

###########################
### DONNÉES DU PROBLÈME ###
###########################

matieres = {
    "Histoire": 4,
    "Maths": 6,
    "Physique-Chimie": 6,
    "Philosophie": 4,
    "Sport": 3,
    "Anglais": 3,
    "Espagnol": 2,
    "Maths expertes": 2
}

# Créneaux horaires disponibles

jours_str = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
nb_jours = len(jours_str)

heures_str = ["8h30-9h30", "9h30-10h30", "10h30-11h30", "11h30-12h30", "14h-15h", "15h-16h", "16h-17h", "17h-18h"]
nb_heures = len(heures_str)

# Nombre de classes et salles
nb_classes = 5
nb_salles = 4

########################
### MODÉLISATION CSP ###
########################

# Modèle CSP
model = cp_model.CpModel()


#################
### VARIABLES ###
#################

# x[cours, jour, heure, classe, salle] = 1 si le cours est programmé à ce créneau, sinon 0
x = {}
for nom_matiere in matieres:
    for jour in range(nb_jours):
        for heure in range(nb_heures):
            for classe in range(nb_classes):
                for salle in range(nb_salles):
                    x[(nom_matiere, jour, heure, classe, salle)] = model.NewBoolVar(
                        f'{nom_matiere}_{jour}_{heure}_classe{classe}_salle{salle}')


###################
### CONTRAINTES ###
###################

# 1. Chaque classe doit avoir le nombre d'nb_heures requis par semaine pour chaque cours
for nom_matiere, heures_matiere in matieres.items():
    for classe in range(nb_classes):
        model.Add(sum(x[(nom_matiere, jour, heure, classe, salle)]
                      for jour in range(nb_jours)
                      for heure in range(nb_heures)
                      for salle in range(nb_salles)) == heures_matiere)

# 2. Une classe ne peut pas avoir deux cours en même temps
for jour in range(nb_jours):
    for heure in range(nb_heures):
        for classe in range(nb_classes):
            model.Add(sum(x[(nom_matiere, jour, heure, classe, salle)]
                          for nom_matiere in matieres
                          for salle in range(nb_salles)) <= 1)

# 3. Une salle ne peut pas être utilisée par deux cours en même temps
for jour in range(nb_jours):
    for heure in range(nb_heures):
        for salle in range(nb_salles):
            model.Add(
                sum(x[(nom_matiere, jour, heure, classe, salle)]
                    for nom_matiere in matieres
                    for classe in range(nb_classes)) <= 1
            )

# 4. Un même cours ne peut pas être enseigné dans deux classes différentes au même moment
# (pour représenter la disponibilité des enseignants)
for nom_matiere in matieres:
    for jour in range(nb_jours):
        for heure in range(nb_heures):
            model.Add(sum(x[(nom_matiere, jour, heure, classe, salle)]
                          for classe in range(nb_classes)
                          for salle in range(nb_salles)) <= 1)

# 5. Pas plus de deux nb_heures d'un même cours à la suite pour une classe
for nom_matiere in matieres:
    for jour in range(nb_jours):
        for heure in range(nb_heures - 2):
            for classe in range(nb_classes):
                model.Add(
                    sum(x[(nom_matiere, jour, heure, classe, salle)] for salle in range(nb_salles)) +
                    sum(x[(nom_matiere, jour, heure + 1, classe, salle)] for salle in range(nb_salles)) +
                    sum(x[(nom_matiere, jour, heure + 2, classe, salle)] for salle in range(nb_salles)) < 3
                )

# 6. Pas de cours de deux heures dans une salle differente
for nom_matiere in matieres:
    for jour in range(nb_jours):
        for heure in range(nb_heures - 1):
            for classe in range(nb_classes):
                for salle1 in range(nb_salles):
                    for salle2 in range(nb_salles):
                        # Si au moins un des deux cours n'existe pas, la condition est validée
                        if salle1 != salle2:
                            model.Add(
                                x[(nom_matiere, jour, heure, classe, salle1)] +
                                x[(nom_matiere, jour, heure + 1, classe, salle2)] <= 1
                            )



####################
### MINIMISATION ###
####################

# 7. Minimiser les "trous" pour les élèves

# On créé Y[c, j, h] = 1 si la classe c a un cours (de n'importe quelle matière) le jour j à l'heure h.
Y = {}
for classe in range(nb_classes):
    for jour in range(nb_jours):
        for heure in range(nb_heures):
            Y[(classe, jour, heure)] = model.NewBoolVar(f"Y_classe{classe}_{jour}_{heure}")
            model.Add(Y[(classe, jour, heure)] ==
                sum(x[(nom_matiere, jour, heure, classe, salle)]
                    for nom_matiere in matieres
                    for salle in range(nb_salles)
                    )
                )


trous = []
for classe in range(nb_classes):
    for jour in range(nb_jours):
        # Pour les trous d'une heure
        # On créé trou1 = pattern "cours - pas cours - cours"
        for heure in range(nb_heures - 2):
            trou1 = model.NewBoolVar(f"trou1_classe{classe}_{jour}_{heure}")
            # Assure que trou != 1 si la classe :
            # - n'a pas cours a l'heure h
            # - OU a cours à l'heure h+1
            # - OU n'a pas cours a l'heure h+2
            model.Add(trou1 <= Y[(classe, jour, heure)])
            model.Add(trou1 <= 1 - Y[(classe, jour, heure + 1)])
            model.Add(trou1 <= Y[(classe, jour, heure + 2)])
            # Assure que trou = 1 si la classe :
            # - a cours a l'heure h
            # - ET n'a pas cours à l'heure h+1
            # - ET a cours a l'heure h+2
            model.Add(trou1 >= Y[(classe, jour, heure)]
                      + (1 - Y[(classe, jour, heure + 1)])
                      + Y[(classe, jour, heure + 2)] - 2)
            trous.append(trou1)

        # Pour les trous de deux heures
        # On créé trou2 = pattern "cours - pas cours - pas cours - cours"
        for heure in range(nb_heures - 3):
            trou2 = model.NewBoolVar(f"trou2_classe{classe}_{jour}_{heure}")
            # Même logique en prenant deux heures de trous de plus en compte
            model.Add(trou2 <= Y[(classe, jour, heure)])
            model.Add(trou2 <= 1 - Y[(classe, jour, heure + 1)])
            model.Add(trou2 <= 1 - Y[(classe, jour, heure + 2)])
            model.Add(trou2 <= Y[(classe, jour, heure + 3)])
            model.Add(trou2 >= Y[(classe, jour, heure)]
                      + (1 - Y[(classe, jour, heure + 1)])
                      + (1 - Y[(classe, jour, heure + 2)])
                      + Y[(classe, jour, heure + 3)] - 3)
            trous.append(trou2)

            # Pour les trous de trois heures
            # On créé trou3 = pattern "cours - pas cours - pas cours - pas cours - cours"
            for heure in range(nb_heures - 4):
                trou3 = model.NewBoolVar(f"trou3_classe{classe}_{jour}_{heure}")
                # Même logique en prenant trois heures de trous de plus en compte
                model.Add(trou3 <= Y[(classe, jour, heure)])
                model.Add(trou3 <= 1 - Y[(classe, jour, heure + 1)])
                model.Add(trou3 <= 1 - Y[(classe, jour, heure + 2)])
                model.Add(trou3 <= 1 - Y[(classe, jour, heure + 3)])
                model.Add(trou3 <= Y[(classe, jour, heure + 4)])
                model.Add(trou3 >= Y[(classe, jour, heure)]
                          + (1 - Y[(classe, jour, heure + 1)])
                          + (1 - Y[(classe, jour, heure + 2)])
                          + (1 - Y[(classe, jour, heure + 3)])
                          + Y[(classe, jour, heure + 4)] - 4)
                trous.append(trou3)

            # Pour les trous de quatre heures
            # On créé trou4 = pattern "cours - pas cours - pas cours - pas cours - pas cours - cours"
            for heure in range(nb_heures - 5):
                trou4 = model.NewBoolVar(f"trou4_classe{classe}_{jour}_{heure}")
                # Même logique en prenant quatre heures de trous de plus en compte
                model.Add(trou4 <= Y[(classe, jour, heure)])
                model.Add(trou4 <= 1 - Y[(classe, jour, heure + 1)])
                model.Add(trou4 <= 1 - Y[(classe, jour, heure + 2)])
                model.Add(trou4 <= 1 - Y[(classe, jour, heure + 3)])
                model.Add(trou4 <= 1 - Y[(classe, jour, heure + 4)])
                model.Add(trou4 <= Y[(classe, jour, heure + 5)])
                model.Add(trou4 >= Y[(classe, jour, heure)]
                    + (1 - Y[(classe, jour, heure + 1)])
                    + (1 - Y[(classe, jour, heure + 2)])
                    + (1 - Y[(classe, jour, heure + 3)])
                    + (1 - Y[(classe, jour, heure + 4)])
                    + Y[(classe, jour, heure + 5)] - 5)
                trous.append(trou4)

# 8. Minimiser les cours après 17h
# On met un coût pour chaque cours planifié après 17h
cours_tardifs = []
dernier_cours = nb_heures - 1  # 17h00-18h00
for classe in range(nb_classes):
    for nom_matiere in matieres:
        for jour in range(nb_jours):
            for salle in range(nb_salles):
                ct = model.NewBoolVar(f"cours_tardif_classe{classe}_{nom_matiere}_{jour}")
                model.Add(ct == x[(nom_matiere, jour, dernier_cours, classe, salle)])
                cours_tardifs.append(ct)

two_hour_courses = []
single_hour_courses = []

for classe in range(nb_classes):
    for nom_matiere in matieres:
        for jour in range(nb_jours):
            for heure in range(nb_heures - 1):  # Permet de vérifier les paires d'heures
                # Variable pour cours de deux heures consécutives
                two_hour_course = model.NewBoolVar(f"two_hour_course_{classe}_{nom_matiere}_{jour}_{heure}")

                # Vérifier si le cours a lieu sur deux heures consécutives
                model.Add(two_hour_course <= sum(x[(nom_matiere, jour, heure, classe, salle)]
                                                 for salle in range(nb_salles)))
                model.Add(two_hour_course <= sum(x[(nom_matiere, jour, heure + 1, classe, salle)]
                                                 for salle in range(nb_salles)))
                model.Add(two_hour_course >= sum(x[(nom_matiere, jour, heure, classe, salle)]
                                                 for salle in range(nb_salles))
                          + sum(x[(nom_matiere, jour, heure + 1, classe, salle)]
                                for salle in range(nb_salles)) - 1)

                two_hour_courses.append(two_hour_course)

            # Variables pour cours d'une seule heure
            for heure in range(nb_heures):
                # Cours d'une seule heure
                single_hour_course = model.NewBoolVar(f"single_hour_course_{classe}_{nom_matiere}_{jour}_{heure}")

                # Un cours d'une heure est un cours qui n'a pas de cours de la même matière
                # ni avant ni après
                cours_heure_courante = sum(x[(nom_matiere, jour, heure, classe, salle)]
                                           for salle in range(nb_salles))

                # Pour la première heure
                if heure == 0:
                    model.Add(single_hour_course <= cours_heure_courante)
                    model.Add(single_hour_course <= 1 - sum(x[(nom_matiere, jour, heure + 1, classe, salle)]
                                                            for salle in range(nb_salles)))

                # Pour la dernière heure
                elif heure == nb_heures - 1:
                    model.Add(single_hour_course <= cours_heure_courante)
                    model.Add(single_hour_course <= 1 - sum(x[(nom_matiere, jour, heure - 1, classe, salle)]
                                                            for salle in range(nb_salles)))

                # Pour les heures du milieu
                else:
                    model.Add(single_hour_course <= cours_heure_courante)
                    model.Add(single_hour_course <= 1 - sum(x[(nom_matiere, jour, heure - 1, classe, salle)]
                                                            for salle in range(nb_salles)))
                    model.Add(single_hour_course <= 1 - sum(x[(nom_matiere, jour, heure + 1, classe, salle)]
                                                            for salle in range(nb_salles)))

                single_hour_courses.append(single_hour_course)

# On minimise
#    - Priorité : réduire le nombre de trous (chaque trou = 10)
#    - Second : éviter les cours après 17h (coût = 2)
#    - Troisième : minimiser les cours cours d'une seule heure et maximiser les cours de deux heures

model.Minimize(10 * sum(trous) + 5 * sum(cours_tardifs) + 3 * sum(single_hour_courses) - sum(two_hour_courses))


##################
### RESOLUTION ###
##################

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 30.0
status = solver.Solve(model)


##################
### RESULTATS ####
##################

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print("Solution trouvée :")
    print(f"Coût objectif = {solver.ObjectiveValue()} (plus petit = mieux)")

    # Affichage par classe
    for classe in range(nb_classes):
        print(f"\n===== EMPLOI DU TEMPS CLASSE {classe} =====")

        # Créer une matrice d'emploi du temps vide
        edt = {}
        for jour in range(nb_jours):
            edt[jour] = {}
            for heure in range(nb_heures):
                edt[jour][heure] = "---"

        # Remplir la matrice
        for nom_matiere in matieres:
            for jour in range(nb_jours):
                for heure in range(nb_heures):
                    for salle in range(nb_salles):
                        if solver.BooleanValue(x[(nom_matiere, jour, heure, classe, salle)]):
                            edt[jour][heure] = f"{nom_matiere} (Salle {salle})"

        # Afficher la matrice
        print(f"{'Horaire':12}", end="")
        for jour in range(nb_jours):
            print(f"{jours_str[jour]:28}", end="")
        print()

        for heure in range(nb_heures):
            print(f"{heures_str[heure]:12}", end="")
            for jour in range(nb_jours):
                print(f"{edt[jour][heure]:28}", end="")
            print()

        # Vérification du nombre d'nb_heures par matière
        print("\nRécapitulatif des nb_heures par matière:")
        for nom_matiere, heures_matiere in matieres.items():
            heures_planifiees = sum(1 for jour in range(nb_jours) for heure in range(nb_heures) for salle in range(nb_salles)
                                    if solver.BooleanValue(x[(nom_matiere, jour, heure, classe, salle)]))
            print(f"{nom_matiere}: {heures_planifiees}/{heures_matiere} nb_heures")
else:
    print("Aucune solution trouvée.")