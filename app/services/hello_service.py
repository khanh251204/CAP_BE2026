class HelloService:
    @staticmethod
    def get_message():
        return {
            "success": True,
            "message": "Hello Expense Tracker API!"
        }