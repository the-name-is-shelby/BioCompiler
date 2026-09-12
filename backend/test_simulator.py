from parts_library import default_repressilator_model, default_toggle_model, incoherent_feedforward_loop_model, validate_model
from simulator import simulate

for name, model in [("Repressilator", default_repressilator_model()),
                     ("Toggle switch", default_toggle_model()),
                     ("Feed-forward loop", incoherent_feedforward_loop_model())]:
    ok, msg = validate_model(model)
    result = simulate(model)
    print(f"{name}: whitelist_ok={ok}, simulation_success={result['success']}")