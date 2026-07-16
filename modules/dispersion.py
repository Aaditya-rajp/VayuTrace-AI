import math

def calculate_plume_impact(source_lat: float, source_lon: float, target_lat: float, target_lon: float, wind_spd: float, wind_dir: float, source_strength: float = 100.0) -> float:
    """
    Calculates PM2.5 concentration at a target location using a Gaussian Plume Model 
    (Pasquill-Gifford Stability Class D - Neutral).
    """
    wind_spd = max(wind_spd, 0.5) # Prevent zero-division
    
    # Convert degrees to meters (approx 111,320m per degree)
    dy = (target_lat - source_lat) * 111320.0
    dx = (target_lon - source_lon) * 111320.0 * math.cos(math.radians(source_lat))
    
    dist = math.sqrt(dx**2 + dy**2)
    if dist < 50: 
        return 0.0 # Too close for standard Gaussian assumptions
        
    # Vector heading math
    plume_dir = (wind_dir + 180) % 360
    target_angle = (90 - math.degrees(math.atan2(dy, dx))) % 360
    angle_diff = abs((plume_dir - target_angle + 180) % 360 - 180)
    
    # Cross-wind (y) and Down-wind (x) distances
    y = dist * math.sin(math.radians(angle_diff))
    x = dist * math.cos(math.radians(angle_diff))
    
    if x <= 0: 
        return 0.0 # Target is upwind
        
    # Pasquill-Gifford Class D dispersion coefficients
    sigma_y = 0.08 * x * (1 + 0.0001 * x)**(-0.5)
    sigma_z = 0.06 * x * (1 + 0.0015 * x)**(-0.5)
    
    try:
        concentration = (source_strength / (math.pi * wind_spd * sigma_y * sigma_z)) * math.exp(-0.5 * (y / sigma_y)**2)
        return concentration
    except OverflowError:
        return 0.0