"""
Estilos CSS para los carruseles de Bootstrap en Home
"""

CAROUSEL_CSS = """
body {
    margin: 0;
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: transparent;
}

.section-header {
    font-size: 1.5rem;
    font-weight: 600;
    color: #333;
    margin-bottom: 1rem;
    text-align: center;
}

.carousel {
    max-width: 100%;
    margin: 0 auto;
    position: relative;
    padding: 0 60px;
}

.tool-card {
    background: white;
    border-radius: 12px;
    border: 1px solid #e0e0e0;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    min-height: 320px;
    max-width: 400px;
    width: 100%;
    margin: 20px auto;
}

.tool-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.12);
}

/* Bordes de color por categoría */
.card-blue { border-left: 5px solid #1976D2; }
.card-red { border-left: 5px solid #D32F2F; }
.card-orange { border-left: 5px solid #F57C00; }
.card-green { border-left: 5px solid #388E3C; }
.card-teal { border-left: 5px solid #00796B; }
.card-gray { border-left: 5px solid #616161; }
.card-lime { border-left: 5px solid #689F38; }

.card-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #333;
    margin-bottom: 0.8rem;
}

.card-text {
    font-size: 0.95rem;
    color: #666;
    line-height: 1.6;
    margin-bottom: 1rem;
}

.card-features {
    font-size: 0.9rem;
    color: #555;
    padding-left: 1.2rem;
    margin-bottom: 0;
}

.card-features li {
    margin-bottom: 0.4rem;
}

/* Flechas fuera de la card */
.carousel-control-prev,
.carousel-control-next {
    width: 50px;
    height: 50px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 1;
}

.carousel-control-prev {
    left: 0;
}

.carousel-control-next {
    right: 0;
}

/* Solo flecha verde BUCHI, sin fondo ni borde */
.carousel-control-prev-icon,
.carousel-control-next-icon {
    background-color: transparent;
    background-image: none;
    width: 40px;
    height: 40px;
    border: none;
    transition: all 0.3s ease;
}

.carousel-control-prev-icon::before {
    content: '';
    display: inline-block;
    width: 15px;
    height: 15px;
    border-left: 4px solid #64B445;
    border-bottom: 4px solid #64B445;
    transform: rotate(45deg);
}

.carousel-control-next-icon::before {
    content: '';
    display: inline-block;
    width: 15px;
    height: 15px;
    border-right: 4px solid #64B445;
    border-bottom: 4px solid #64B445;
    transform: rotate(-45deg);
}

.carousel-control-prev-icon:hover::before {
    border-color: #289A93;
}

.carousel-control-next-icon:hover::before {
    border-color: #289A93;
}

/* Indicadores en verde BUCHI */
.carousel-indicators button {
    background-color: #64B445;
}
"""