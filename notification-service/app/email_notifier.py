import time

class EmailNotifier:
    @staticmethod
    def send_order_confirmation(email: str, order_id: int, total: float, items: list):
        print(f"[EMAIL] Iniciando proceso de envío para: {email}")
        time.sleep(0.1) 
        print("--------------------------------------------------")
        print(f"📧 CORREO ENVIADO EXITOSAMENTE A: {email}")
        print(f"📦 Pedido ID: {order_id}")
        print(f"🛍️ Productos: {', '.join(items)}")
        print(f"💰 Total procesado: ${total:.2f}")
        print("--------------------------------------------------")
        return True