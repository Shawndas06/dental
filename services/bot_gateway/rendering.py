from shared.service_visits import visit_type_for_service
from shared.schemas import Button, Screen

BACK = Button(text="Назад", callback_data="nav:back")
HOME = Button(text="Главное меню", callback_data="menu:main")


def _footer() -> list[Button]:
    return [BACK, HOME]


def welcome_screen(display_name: str | None = None) -> Screen:
    greeting = display_name or "гость"
    return Screen(
        text=(
            f"Добро пожаловать, {greeting}.\n\n"
            "Демо стоматология — запись, цены и напоминания в одном боте.\n\n"
            "Нажмите «Продолжить» для быстрой регистрации (без форм)."
        ),
        buttons=[
            Button(text="Продолжить", callback_data="register:confirm"),
            Button(text="Контакты клиники", callback_data="menu:contacts"),
        ],
        button_layout=[1, 1],
    )


def main_menu() -> Screen:
    return Screen(
        text="Демо стоматология\n\nВыберите раздел:",
        buttons=[
            Button(text="Записаться", callback_data="appointment:start"),
            Button(text="Мои записи", callback_data="appointment:list"),
            Button(text="Цены", callback_data="pricing:list"),
            Button(text="Контакты", callback_data="menu:contacts"),
            Button(text="Календарь врача", callback_data="calendar:doctor:today"),
        ],
        button_layout=[2, 2, 1],
    )


def registration_done_screen(name: str) -> Screen:
    return Screen(
        text=f"Регистрация завершена, {name}.\n\nТеперь можно записаться на приём.",
        buttons=[
            Button(text="Записаться", callback_data="appointment:start"),
            HOME,
        ],
        button_layout=[1, 1],
    )


def contacts_screen(clinic_phone: str) -> Screen:
    return Screen(
        text=f"Контакты клиники\n\nТелефон: {clinic_phone}",
        buttons=_footer(),
        button_layout=[2],
    )


def services_screen(services: list[dict]) -> Screen:
    buttons = [
        Button(text=item["name"], callback_data=f"service:select:{item['service_id']}")
        for item in services
    ]
    buttons.extend(_footer())
    return Screen(
        text="Запись на приём\n\nВыберите услугу:",
        buttons=buttons,
        button_layout=None,
    )


def slots_screen(slots: list[dict], service_id: str) -> Screen:
    buttons = [
        Button(
            text=f"{slot['date']}  {slot['time'][:5]}",
            callback_data=f"slot:select:{slot['slot_id']}",
        )
        for slot in slots
    ]
    buttons.extend(_footer())
    return Screen(
        text="Свободные слоты\n\nЗапись создаётся только после выбора времени.",
        buttons=buttons,
        conversation_state={
            "serviceId": service_id,
            "visitType": visit_type_for_service(service_id),
        },
    )


def appointments_screen(lines: list[str], action_buttons: list[Button]) -> Screen:
    buttons = list(action_buttons)
    buttons.extend(_footer())
    return Screen(
        text="Ваши записи\n\n" + "\n".join(lines),
        buttons=buttons,
    )


def pricing_screen(lines: list[str]) -> Screen:
    return Screen(
        text="Прайс-лист\n\n" + "\n".join(lines),
        buttons=_footer(),
        button_layout=[2],
    )


def simple_screen(text: str, extra_buttons: list[Button] | None = None, layout: list[int] | None = None) -> Screen:
    buttons = list(extra_buttons or [])
    if not any(button.callback_data == HOME.callback_data for button in buttons):
        buttons.append(HOME)
    return Screen(text=text, buttons=buttons, button_layout=layout)


def _chunk_buttons(buttons: list[Button], layout: list[int] | None) -> list[list[Button]]:
    if not buttons:
        return []
    if layout:
        rows: list[list[Button]] = []
        index = 0
        for width in layout:
            row = buttons[index : index + width]
            if not row:
                break
            rows.append(row)
            index += width
        if index < len(buttons):
            rows.append(buttons[index:])
        return rows
    return [[button] for button in buttons]


def to_telegram_markup(screen: Screen | list[Button], layout: list[int] | None = None):
    if isinstance(screen, Screen):
        buttons = screen.buttons
        layout = screen.button_layout
    else:
        buttons = screen
    rows = _chunk_buttons(buttons, layout)
    if not rows:
        return None
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=button.text, callback_data=button.callback_data) for button in row]
                for row in rows
            ]
        )
    except ModuleNotFoundError:
        return {
            "inline_keyboard": [
                [{"text": button.text, "callback_data": button.callback_data} for button in row] for row in rows
            ]
        }
