from cornice import Service

appsync = Service(name='appsync', path='/')


@appsync.api()
def hello(request):
    return {}
