use wasm_bindgen::prelude::*;
use web_sys::{CanvasRenderingContext2d, HtmlCanvasElement, ImageData};

#[wasm_bindgen]
pub fn render_dicom_image(
    canvas: HtmlCanvasElement,
    data: Vec<u8>,
    width: u32,
    height: u32,
) -> Result<(), JsValue> {
    let context = canvas
        .get_context("2d")?
        .unwrap()
        .dyn_into::<CanvasRenderingContext2d>()?;

    canvas.set_width(width);
    canvas.set_height(height);

    let mut rgba_data = Vec::with_capacity((width * height * 4) as usize);
    for &gray in &data {
        rgba_data.push(gray);
        rgba_data.push(gray);
        rgba_data.push(gray);
        rgba_data.push(255);
    }

    let image_data = ImageData::new_with_u8_clamped_array_and_sh(
        wasm_bindgen::Clamped(&rgba_data),
        width,
        height,
    )?;

    context.put_image_data(&image_data, 0.0, 0.0)?;

    Ok(())
}
