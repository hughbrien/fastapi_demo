2# Fast API Frontend Service 

### Language : Python
 
- You are an experienced Python Engineer / Developer.  You are building a FastAPI service that does the following services.
-    
-   They can use the following baseurl as the mock http://localhost:9000. : 

Create a basic User Interface that will call the following services with a simple User Interface 

- Create the following services
-   Basic Authentication Service - This is a mock service.  Also pretend you are call a remote Authenticaiton servcie that return a Auth Token 
-   Rag Service Call to Ollama  qwen2.5:latest  
-   AI Chat API call to Ollama  llama3.2:latest

Use  LiteLLM with both the Rag and Chat calls.  
Add Anthopic as an additional LLM / AI  


### Observaiblity 
Provide observability usign TraceLoop.
There is a local otel collector : otelcontribcol is running with basic configuration 


### Documents for RAG 

```
corpus_of_documents = [
    "Take a leisurely walk in the park and enjoy the fresh air.",
    "Visit a local museum and discover something new.",
    "Attend a live music concert and feel the rhythm.",
    "Go for a hike and admire the natural scenery.",
    "Have a picnic with friends and share some laughs.",
    "Explore a new cuisine by dining at an ethnic restaurant.",
    "Take a yoga class and stretch your body and mind.",
    "Join a local sports league and enjoy some friendly competition.",
    "Attend a workshop or lecture on a topic you're interested in.",
    "Visit an amusement park and ride the roller coasters."
]

```


