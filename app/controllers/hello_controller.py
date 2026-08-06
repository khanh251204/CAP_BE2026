from app.services.hello_service import HelloService


class HelloController:

    @staticmethod
    def hello():
        return HelloService.get_message()