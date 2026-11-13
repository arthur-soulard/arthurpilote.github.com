# Sécurité

## Versions suivies

Seule la dernière version publiée de Pilote reçoit des corrections. Les versions
installées se mettent à jour automatiquement.

## Signaler une faille

Merci de ne pas ouvrir de ticket public. Écris à **arthur.economie@gmail.com** avec :

- la version de Pilote et le système (Windows ou Mac) ;
- les étapes pour reproduire le problème ;
- ce qu'un attaquant pourrait obtenir.

Tu recevras une réponse sous une semaine. Une faille confirmée est corrigée dans une
nouvelle version, et la fiche de cette version le mentionne.

## Ce que Pilote protège, et ce qu'il ne protège pas

- Le serveur local (127.0.0.1) refuse les pages web étrangères : jeton de session, refus
  des `Origin` et `Host` étrangers.
- La page locale ne contient plus le jeton : seule la fenêtre de Pilote peut le demander.
  Un autre programme de ton ordinateur, ou un autre compte Windows, ne peut donc plus lire
  tes données par le serveur local. Pilote ne protège pas pour autant contre un programme
  malveillant déjà installé sur ta session : il peut lire les fichiers directement.
- Les fichiers de données ne sont pas chiffrés ; le code PIN ne fait que séparer les
  utilisateurs dans l'app.
