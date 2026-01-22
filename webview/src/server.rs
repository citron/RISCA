use actix_web::{web, App, HttpResponse, HttpServer, Result};
use actix_files as fs;
use actix_cors::Cors;
use serde::Serialize;
use std::path::PathBuf;
use std::collections::HashMap;
use dicom::object::open_file;
use dicom::pixeldata::PixelDecoder;

#[derive(Serialize)]
struct FileEntry {
    name: String,
    path: String,
    is_dir: bool,
}

#[derive(Serialize, Clone)]
struct DicomSeriesInfo {
    series_uid: String,
    series_description: String,
    modality: String,
    image_count: usize,
    images: Vec<String>,
}

#[derive(Serialize, Clone)]
struct DicomStudyInfo {
    study_uid: String,
    study_description: String,
    study_date: String,
    series: HashMap<String, DicomSeriesInfo>,
}

#[derive(Serialize)]
struct DicomPatientInfo {
    patient_id: String,
    patient_name: String,
    studies: HashMap<String, DicomStudyInfo>,
}

#[derive(Serialize)]
struct DicomTreeResponse {
    patients: HashMap<String, DicomPatientInfo>,
}

#[derive(Serialize)]
struct DicomInfo {
    patient_name: String,
    study_date: String,
    modality: String,
    rows: u32,
    cols: u32,
    bits_allocated: u32,
    bits_stored: u32,
    photometric_interpretation: String,
}

#[derive(Serialize)]
struct DicomPixelData {
    width: u32,
    height: u32,
    data: Vec<u8>,
}

async fn get_dicom_tree() -> Result<HttpResponse> {
    let base_path = PathBuf::from("/home/gacquewi/dicom");
    let mut patients: HashMap<String, DicomPatientInfo> = HashMap::new();
    
    fn scan_directory(dir: &PathBuf, patients: &mut HashMap<String, DicomPatientInfo>) {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                
                if path.is_dir() {
                    scan_directory(&path, patients);
                } else if let Ok(obj) = open_file(&path) {
                    let patient_id = obj.element_by_name("PatientID")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "UNKNOWN".to_string());
                    
                    let patient_name = obj.element_by_name("PatientName")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "Unknown".to_string());
                    
                    let study_uid = obj.element_by_name("StudyInstanceUID")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "UNKNOWN_STUDY".to_string());
                    
                    let study_description = obj.element_by_name("StudyDescription")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "".to_string());
                    
                    let study_date = obj.element_by_name("StudyDate")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "Unknown".to_string());
                    
                    let series_uid = obj.element_by_name("SeriesInstanceUID")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "UNKNOWN_SERIES".to_string());
                    
                    let series_description = obj.element_by_name("SeriesDescription")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "".to_string());
                    
                    let modality = obj.element_by_name("Modality")
                        .ok()
                        .and_then(|e| e.to_str().ok())
                        .map(|s| s.to_string())
                        .unwrap_or_else(|| "Unknown".to_string());
                    
                    let relative_path = path.strip_prefix("/home/gacquewi/dicom")
                        .unwrap_or(&path)
                        .to_string_lossy()
                        .to_string();
                    
                    let patient = patients.entry(patient_id.clone()).or_insert(DicomPatientInfo {
                        patient_id: patient_id.clone(),
                        patient_name: patient_name.clone(),
                        studies: HashMap::new(),
                    });
                    
                    let study = patient.studies.entry(study_uid.clone()).or_insert(DicomStudyInfo {
                        study_uid: study_uid.clone(),
                        study_description,
                        study_date,
                        series: HashMap::new(),
                    });
                    
                    let series = study.series.entry(series_uid.clone()).or_insert(DicomSeriesInfo {
                        series_uid: series_uid.clone(),
                        series_description,
                        modality,
                        image_count: 0,
                        images: Vec::new(),
                    });
                    
                    series.images.push(relative_path);
                    series.image_count = series.images.len();
                }
            }
        }
    }
    
    scan_directory(&base_path, &mut patients);
    
    Ok(HttpResponse::Ok().json(DicomTreeResponse { patients }))
}

async fn list_files(path: web::Path<String>) -> Result<HttpResponse> {
    let base_path = PathBuf::from("/home/gacquewi/dicom");
    let requested_path = path.into_inner();
    
    let full_path = if requested_path.is_empty() {
        base_path.clone()
    } else {
        base_path.join(&requested_path)
    };

    if !full_path.starts_with(&base_path) {
        return Ok(HttpResponse::Forbidden().json("Access denied"));
    }

    let mut entries = Vec::new();
    
    if let Ok(dir_entries) = std::fs::read_dir(&full_path) {
        for entry in dir_entries.flatten() {
            if let Ok(metadata) = entry.metadata() {
                let name = entry.file_name().to_string_lossy().to_string();
                let relative_path = if requested_path.is_empty() {
                    name.clone()
                } else {
                    format!("{}/{}", requested_path, name)
                };
                
                entries.push(FileEntry {
                    name,
                    path: relative_path,
                    is_dir: metadata.is_dir(),
                });
            }
        }
    }

    entries.sort_by(|a, b| {
        match (a.is_dir, b.is_dir) {
            (true, false) => std::cmp::Ordering::Less,
            (false, true) => std::cmp::Ordering::Greater,
            _ => a.name.cmp(&b.name),
        }
    });

    Ok(HttpResponse::Ok().json(entries))
}

async fn get_dicom_info(path: web::Path<String>) -> Result<HttpResponse> {
    let base_path = PathBuf::from("/home/gacquewi/dicom");
    let file_path = base_path.join(path.into_inner());

    if !file_path.starts_with(&base_path) {
        return Ok(HttpResponse::Forbidden().json("Access denied"));
    }

    match open_file(&file_path) {
        Ok(obj) => {
            let patient_name = obj.element_by_name("PatientName")
                .ok()
                .and_then(|e| e.to_str().ok())
                .map(|s| s.to_string())
                .unwrap_or_else(|| "Unknown".to_string());
            
            let study_date = obj.element_by_name("StudyDate")
                .ok()
                .and_then(|e| e.to_str().ok())
                .map(|s| s.to_string())
                .unwrap_or_else(|| "Unknown".to_string());
            
            let modality = obj.element_by_name("Modality")
                .ok()
                .and_then(|e| e.to_str().ok())
                .map(|s| s.to_string())
                .unwrap_or_else(|| "Unknown".to_string());
            
            let rows = obj.element_by_name("Rows")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(0);
            
            let cols = obj.element_by_name("Columns")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(0);
            
            let bits_allocated = obj.element_by_name("BitsAllocated")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(16);
            
            let bits_stored = obj.element_by_name("BitsStored")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(16);
            
            let photometric_interpretation = obj.element_by_name("PhotometricInterpretation")
                .ok()
                .and_then(|e| e.to_str().ok())
                .map(|s| s.to_string())
                .unwrap_or_else(|| "MONOCHROME2".to_string());

            Ok(HttpResponse::Ok().json(DicomInfo {
                patient_name,
                study_date,
                modality,
                rows,
                cols,
                bits_allocated,
                bits_stored,
                photometric_interpretation,
            }))
        }
        Err(e) => Ok(HttpResponse::BadRequest().json(format!("Error reading DICOM: {}", e))),
    }
}

async fn get_dicom_image(path: web::Path<String>) -> Result<HttpResponse> {
    let base_path = PathBuf::from("/home/gacquewi/dicom");
    let file_path = base_path.join(path.into_inner());

    if !file_path.starts_with(&base_path) {
        return Ok(HttpResponse::Forbidden().json("Access denied"));
    }

    match open_file(&file_path) {
        Ok(obj) => {
            let rows = obj.element_by_name("Rows")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(0);
            
            let cols = obj.element_by_name("Columns")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(0);
            
            let bits_allocated = obj.element_by_name("BitsAllocated")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(16);
            
            let photometric = obj.element_by_name("PhotometricInterpretation")
                .ok()
                .and_then(|e| e.to_str().ok())
                .map(|s| s.to_string())
                .unwrap_or_else(|| "MONOCHROME2".to_string());
            
            let samples_per_pixel = obj.element_by_name("SamplesPerPixel")
                .ok()
                .and_then(|e| e.to_int::<u32>().ok())
                .unwrap_or(1);

            match obj.decode_pixel_data() {
                Ok(decoded) => {
                    let data = decoded.data();
                    let total_pixels = (rows * cols) as usize;
                    
                    let normalized_data: Vec<u8> = if photometric.contains("RGB") || samples_per_pixel == 3 {
                        // Image RGB - copier directement les données
                        let expected_size = total_pixels * 3;
                        if data.len() >= expected_size {
                            data[..expected_size].to_vec()
                        } else {
                            eprintln!("Warning: RGB data size mismatch. Expected {}, got {}", expected_size, data.len());
                            let mut result = vec![0u8; expected_size];
                            let copy_len = data.len().min(expected_size);
                            result[..copy_len].copy_from_slice(&data[..copy_len]);
                            result
                        }
                    } else {
                        // Image en niveau de gris (MONOCHROME)
                        let bytes_per_pixel = if bits_allocated <= 8 { 1 } else { 2 };
                        let expected_size = total_pixels * bytes_per_pixel;
                        
                        let mut pixel_values: Vec<u16> = Vec::new();
                        
                        if bytes_per_pixel == 1 {
                            for &byte in data.iter().take(expected_size) {
                                pixel_values.push(byte as u16);
                            }
                        } else {
                            for i in (0..data.len().min(expected_size)).step_by(2) {
                                if i + 1 < data.len() {
                                    let value = u16::from_le_bytes([data[i], data[i + 1]]);
                                    pixel_values.push(value);
                                }
                            }
                        }
                        
                        if pixel_values.len() != total_pixels {
                            eprintln!("Warning: pixel count mismatch. Expected {}, got {}", total_pixels, pixel_values.len());
                        }
                        
                        let min_val = *pixel_values.iter().min().unwrap_or(&0) as f32;
                        let max_val = *pixel_values.iter().max().unwrap_or(&1) as f32;
                        let range = max_val - min_val;

                        // Convertir en RGB (3 octets par pixel pour uniformité)
                        let mut result = Vec::with_capacity(total_pixels * 3);
                        for &pixel in &pixel_values {
                            let gray = if range > 0.0 {
                                ((pixel as f32 - min_val) / range * 255.0) as u8
                            } else {
                                0
                            };
                            result.push(gray);
                            result.push(gray);
                            result.push(gray);
                        }
                        result
                    };

                    Ok(HttpResponse::Ok().json(DicomPixelData {
                        width: cols,
                        height: rows,
                        data: normalized_data,
                    }))
                }
                Err(e) => Ok(HttpResponse::BadRequest().json(format!("Error decoding pixel data: {}", e))),
            }
        }
        Err(e) => Ok(HttpResponse::BadRequest().json(format!("Error reading DICOM: {}", e))),
    }
}

async fn list_root_files() -> Result<HttpResponse> {
    list_files(web::Path::from(String::new())).await
}

async fn index() -> Result<HttpResponse> {
    let html = include_str!("../static/index.html");
    Ok(HttpResponse::Ok().content_type("text/html").body(html))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("Starting DICOM viewer server on http://localhost:8104");
    println!("Serving files from /home/gacquewi/dicom");

    HttpServer::new(|| {
        let cors = Cors::permissive();
        
        App::new()
            .wrap(cors)
            .route("/", web::get().to(index))
            .route("/api/tree", web::get().to(get_dicom_tree))
            .route("/api/files", web::get().to(list_root_files))
            .route("/api/files/{path:.*}", web::get().to(list_files))
            .route("/api/dicom/info/{path:.*}", web::get().to(get_dicom_info))
            .route("/api/dicom/image/{path:.*}", web::get().to(get_dicom_image))
            .service(fs::Files::new("/static", "./static"))
    })
    .bind(("0.0.0.0", 8104))?
    .run()
    .await
}
