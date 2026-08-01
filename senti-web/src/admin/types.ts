export type Gravedad = "verde" | "amarillo" | "rojo";

export interface AlertaForm {
  titulo: string;
  zona: string;
  fechaHora: string;
  tipoEvento: string;
  descripcion: string;
  recomendacion: string;
  gravedad: Gravedad;
}

export interface DocumentoAdjunto {
  nombre: string;
  tamanoTexto: string;
  fechaTexto: string;
}
