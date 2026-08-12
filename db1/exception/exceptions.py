from __future__ import annotations



class AppException(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class UserAlreadyExists(AppException):
    status_code: int = 409
    detail: str = "User already exists"

class EmailAlreadyExists(AppException):
    status_code: int = 409
    detail: str = "Email already exists"

class InvalidCredentials(AppException):
    status_code: int = 401
    detail: str = "Invalid password or username"

class InvalidTokenException(AppException):
    status_code = 401
    detail = "Token is invalid or expired"


class TokenNotFoundException(AppException):
    status_code = 404
    detail = "Refresh token not found"


class UserNotFound(AppException):
    status_code = 404
    detail = "User not found"

class UserForbidden(AppException):
    status_code = 403
    detail = "Forbidden"

class ProjectNotFound(AppException):
    status_code = 404
    detail = "Project not found"

class ProjectAlreadyExists(AppException):
    status_code = 409
    detail = "Project already exists"

class ProjectForbidden(AppException):
    status_code = 403
    detail = "Project forbidden"

class TaskNotFound(AppException):
    status_code = 404
    detail = "Task not found"

class TaskAlreadyExists(AppException):
    status_code = 409
    detail = "Task already exists"


class TaskForbidden(AppException):
    status_code = 403
    detail = "Task forbidden"

class ProductNotFound(AppException):
    status_code = 404
    detail = "Product not found"


class OutOfStock(AppException):
    status_code = 409
    detail = "Not enough stock"

class InvalidOrderTransition(AppException):
    status_code = 409
    detail = "Invalid order status transition"

class OrderNotFound(AppException):
    status_code = 404
    detail = "Order not found"


class OrderForbidden(AppException):
    status_code = 403
    detail = "Order forbidden"

class UserBanned(AppException):
    status_code = 403
    detail = "Your account has been banned"