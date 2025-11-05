# estimator.py
# Simple estimator functions for minor project

def paint_estimate(wall_area_m2, coverage=10.0, coats=2, wastage=0.1, price_per_litre=250.0):
    """
    wall_area_m2: area to paint (m2)
    coverage: m2 per litre
    coats: number of coats
    wastage: fraction e.g., 0.1 for 10%
    price_per_litre: ₹ per litre
    Returns: (litres_needed, material_cost)
    """
    if wall_area_m2 <= 0:
        return 0.0, 0.0
    litres = (wall_area_m2 / coverage) * coats * (1 + wastage)
    material_cost = litres * price_per_litre
    return round(litres, 2), round(material_cost, 2)

def tiles_estimate(floor_area_m2, wastage=0.05, rate_per_m2=600.0):
    """
    floor_area_m2: area of floor
    wastage: fraction
    rate_per_m2: ₹ per m2 of tiles (material)
    Returns: (area_with_wastage, material_cost)
    """
    if floor_area_m2 <= 0:
        return 0.0, 0.0
    qty = floor_area_m2 * (1 + wastage)
    cost = qty * rate_per_m2
    return round(qty, 2), round(cost, 2)

def plumbing_estimate(num_points=1, base_charge=500.0, per_point=300.0):
    """
    num_points: number of plumbing points (taps, fittings)
    base_charge: fixed callout
    per_point: per-point labour/material estimate
    Returns: total_cost
    """
    if num_points <= 0:
        return 0.0
    total = base_charge + (num_points * per_point)
    return round(total, 2)

def generic_labour(area_m2, labour_rate_per_m2=30.0):
    """
    Simple labour estimate by area
    """
    if area_m2 <= 0:
        return 0.0
    return round(area_m2 * labour_rate_per_m2, 2)
