// PyO3 Python bindings (optional feature gate "python").
// Exposes init_game + step_game + game_to_json for Python training scripts.
#![cfg(feature = "python")]

use pyo3::prelude::*;

/// Initialize a new hex game and return JSON-serialized GameState.
#[pyfunction]
fn init_game_py(seed: u64, generator_id: &str) -> PyResult<String> {
    todo!("Python bindings: init_game")
}

/// Step the game forward and return JSON-serialized GameState.
#[pyfunction]
fn step_game_py(state_json: &str, actions_p0_json: &str, actions_p1_json: &str) -> PyResult<String> {
    todo!("Python bindings: step_game")
}

/// miniciv Python module
#[pymodule]
fn miniciv_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(init_game_py, m)?)?;
    m.add_function(wrap_pyfunction!(step_game_py, m)?)?;
    Ok(())
}
