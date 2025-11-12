from aiogram.fsm.state import State, StatesGroup

class AnalysisStates(StatesGroup):
    waiting_for_link = State()
    waiting_for_receipt = State()
    waiting_for_strategy_choice = State()
    waiting_for_feedback = State()
    in_main_menu = State()