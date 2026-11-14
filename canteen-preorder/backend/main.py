from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import functions
import endpoints

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CATEGORIES = ["breakfast", "meals", "snacks", "beverages", "desserts"]


# Check user authentication and authorization
def check_role(token, allowed_roles):
    username = functions.verify_token(token=token, token_type="access")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    role = functions.get_user_role(username)
    if role is None:
        raise HTTPException(status_code=401, detail="User not found")
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="You do not have permission")
    return username


# Model 1: Add Menu Item
class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1)
    category: str
    price: int = Field(ge=5, le=500)


# Model 2: Update Availability
class AvailabilityUpdate(BaseModel):
    available: int = Field(ge=0, le=1)


# Model 3: Place Order
class OrderCreate(BaseModel):
    roll_no: str = Field(min_length=1)
    item_id: int
    quantity: int = Field(ge=1, le=5)


# Model 4: Login
class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str | None = None   # when given, a new username is registered with this role on first login


# Model 5: Register
class RegisterRequest(BaseModel):
    user_name: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str


# E13 - Register
@app.post("/register")
def register_user(data: RegisterRequest):
    if data.role.strip().lower() not in ["staff", "student"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    if functions.register_user(user_name=data.user_name, password=data.password, role=data.role):
        return {"message": "user registered successfully"}
    raise HTTPException(status_code=400, detail="User already exists")

# E11 - Login
@app.post("/login")
def login(data: LoginRequest):
    if data.role is not None:
        if data.role.strip().lower() not in ["staff", "student"]:
            raise HTTPException(status_code=400, detail="Invalid role")
        # creates the account only if this username is new; an existing user is left as it is
        functions.register_user(user_name=data.username, password=data.password, role=data.role)
    token = functions.verify_login(username=data.username, password=data.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    return token

# E12 - Refresh access token
@app.post("/refresh")
def refresh(refresh_token: str = Header(None)):
    username = functions.verify_token(token=refresh_token, token_type="refresh")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or Expired refresh token")
    return {"access_token": functions.create_token(username=username, token_type="access")}


# E1 - Get Menu
@app.get("/menu")
def menu(category: str = None, available: int = None, token: str = Header(None)):
    check_role(token, ["staff", "student"])
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid category")
    if available is not None and available not in [0, 1]:
        raise HTTPException(status_code=422, detail="Available must be 0 or 1")
    return functions.get_all_menu_items(category=category, available=available)


# E2 - Add Menu Item
@app.post("/menu")
def add_menu(item: MenuItemCreate, token: str = Header(None)):
    check_role(token, ["staff"])
    if item.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid category")
    result = functions.add_menu_item(name=item.name, category=item.category, price=item.price)
    if result is None:
        raise HTTPException(status_code=400, detail="Item already exists")
    return result


# E3 - Update Menu Availability
@app.patch("/menu/{id}/availability")
def update_availability(id: int, data: AvailabilityUpdate, token: str = Header(None)):
    check_role(token, ["staff"])
    result = functions.update_menu_availability(id, data.available)
    if result is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return result


# E4 - Place Order
@app.post("/orders")
def place_order(order: OrderCreate, token: str = Header(None)):
    check_role(token, ["staff", "student"])
    item = functions.get_menu_item(order.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if item["available"] == 0:
        raise HTTPException(status_code=400, detail="This item is sold out today.")
    if len(endpoints.get_student_orders(order.roll_no, active=True)) >= 2:
        raise HTTPException(status_code=400, detail="Student already has 2 active orders")
    return functions.place_order(roll_no=order.roll_no, item_id=order.item_id, quantity=order.quantity)


# E5 - Get One Order
@app.get("/orders/{id}")
def get_order(id: int, token: str = Header(None)):
    check_role(token, ["staff", "student"])
    result = functions.get_order_by_id(id)
    if result is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


# E6 - Get Student's Orders for Today
@app.get("/orders/student/{roll_no}")
def get_student_orders(roll_no: str, token: str = Header(None)):
    check_role(token, ["staff", "student"])
    return endpoints.get_student_orders(roll_no)


# E7 - Move Order to Next Status
@app.patch("/orders/{order_id}/next")
def next_order_status(order_id: int, token: str = Header(None)):
    check_role(token, ["staff"])
    return endpoints.move_order_to_next_status(order_id)


# E8 - Cancel Order
@app.patch("/orders/{order_id}/cancel")
def cancel_order(order_id: int, token: str = Header(None)):
    check_role(token, ["staff", "student"])
    return endpoints.cancel_order(order_id)


# E9 - Get Kitchen Queue
@app.get("/kitchen/queue")
def get_kitchen_queue(token: str = Header(None)):
    check_role(token, ["staff"])
    return endpoints.get_kitchen_queue()


# E10 - Get Today's Sales Summary
@app.get("/kitchen/sales")
def get_today_sales(token: str = Header(None)):
    check_role(token, ["staff"])
    return endpoints.get_today_sales()



# SAMPLE DATA ENDPOINTS
@app.get("/sample-menu")
def sample_menu(token: str = Header(None)):
    check_role(token, ["staff"])
    return functions.menu_items()


@app.get("/sample-orders")
def sample_orders(token: str = Header(None)):
    check_role(token, ["staff"])
    return functions.orders()
