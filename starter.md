
* Une cli avec typer qui permet de lancer différentes expérimentations avec des scénarios décrit dans un json ou autres s'il y a mieux. Mais je dois être en capacité de fournir plusieurs modèles, plusieurs serveur d'inférences (SGLang, llama.cpp, vLLM, etc.), des scénarios avec plusieurs conversation, longueur de prompt généré, etc. 
* Ne cherche pas à réinventer la roue s'il y a des packages qui existe et qui font le job. 
* Il est packager, facilement installable. Car il aura des fonctionnaltié de tests de charge en local (test de charge sur les GPU) et en remote pour calculer ces métriques (TTFT, TPOT, throughput, success rate).
 
| **Catégorie** | **Métrique** | **Description** |
|---|---|---|
| **Latence** | Time to First Token (TTFT) | Temps écoulé entre l'envoi de la requête et la réception du premier token généré. |
| | Time per Output Token (TPOT) | Temps moyen nécessaire pour générer chaque token de sortie après le premier. |
| | End-to-End Latency | Temps total entre l'envoi de la requête et la réception complète de la réponse. |
| | Queue Time | Temps d'attente de la requête dans la file avant son traitement. |
| | Prefill Time | Temps nécessaire pour traiter le prompt d'entrée et calculer le KV cache initial. |
| | Decode Time | Temps total nécessaire pour générer tous les tokens de sortie. |
| **Throughput** | Tokens/sec par requête | Nombre de tokens générés par seconde pour une requête individuelle. |
| | Tokens/sec total | Nombre total de tokens générés par seconde par le système (toutes requêtes confondues). |
| | Requêtes/sec | Nombre de requêtes traitées par le système par seconde. |
| **Fiabilité** | Success Rate | Pourcentage de requêtes complétées avec succès. |
| | Error Rate | Pourcentage de requêtes ayant échoué avec une erreur. |
| | Timeout Rate | Pourcentage de requêtes ayant dépassé le délai d'attente maximum. |
| | Retry Count | Nombre moyen de tentatives nécessaires avant la réussite d'une requête. |
| **Qualité (conversations)** | Cache Hit Rate | Pourcentage de tokens du contexte retrouvés dans le cache KV. |
| | Cache Improvement % | Gain de performance (réduction de latence) grâce au cache. |
| | Turn-to-Turn Latency Ratio | Ratio entre la latence du premier tour et celle des tours suivants dans une conversation. |
| | Context Growth Impact | Impact de l'augmentation de la taille du contexte sur la latence au fil de la conversation. |

D'autres métriques à définir lié aux KV Cache (ça sera surtout pour la partie comparaison entre vLLM & SGLang, par exemple).

* La cli est utilisé pour des objectif de benchmark, donc elle doit fournir l'output qui doit être compatible dataframe. Donc lu facilement par un pandas ou autre paquet de dataframe pour analyser rapidement les résultats. 
* la Cli est configurable : je peux la lancer sur plusieurs host, serveur, fichier de scénarios
* Je peux la lancer sur un serveur ou en remote
* Utilise rich pour l'affichage de la cli
* Elle me permet de tester la connectivité 
* Utiliser pydantic pour la gestion de la configuration 
* Fait des classes courtes pour que le code soit le plus lisible possible. 
* Ecrit et ait ces trois sources de vérité claude.md pour le build, readme.md pour l'utilisateur de la cli, le developper guide pour comprendre comment ça fonctionne, mettre les mains de dedans et contribuer avec une section troubelshooting. Optimise le claude.md pour qu'il soit compréhensible pour toi, et les deux autres fichiers pour qu'ils soient facilement lisible par un être humain. 
* Assure toi qu'il y est une bonne couverture de test 
* Les dépendences sont géré avec uv 
* Créer un make file pour l'install, lancer les tests. pour la partie dev. 
* Créer un guide de packaging. 
* Un exemple d'utilisation. J'ai monter une infrastructure avec 4 Scaleway machines:
- **gpu-llama** (L40S): llama-server GGUF
- **gpu-vllm** (H100): vLLM BF16
- **gpu-sglang** (H100): SGLang BF16
- **gateway** (DEV1-M): LiteLLM, Nginx, Prometheus, Grafana
Je veux évaluer et faire le benchmark des performances de - **Model**: Devstral-Small-2-24B-Instruct-2512 (24B dense) pour montrer la résilience de mon infra, la comparaison de performance entre llama-server GGUF & vLLM BF16 et entre vLLM BF16 & SGLang BF16. 
* Nous allons toujours travailler ensemble à partir d'adr, les adr doivent être lisible par l'humain, elles sont écrites dans le dossier docs/adr, tu préparera un plan d'implémentation qui n'est pas versionné et écrit dans le dossier docs/plan. 
* suit les bonnes pratiques de codes et évite de dupliquer du code


