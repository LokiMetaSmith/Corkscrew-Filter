import math

def calculate_physics():
    # --- Parameters ---
    # Fluid: Air at 25°C, 1 atm
    rho_air = 1.225  # kg/m^3
    mu_air = 1.81e-5 # Pa·s

    # Geometry: 3/4" Tube
    d_tube_mm = 19.05 # mm
    d_tube = d_tube_mm / 1000.0 # m

    # Helical Radius (Tight coil)
    # Assumption: Tightly wound, maybe R_coil ~ 1.5 * D_tube or similar.
    # Text says "tight helical radius". Let's assume ~25mm to 30mm.
    r_coil_mm = 25.0
    r_coil = r_coil_mm / 1000.0

    # Particle: Sugar (Sucrose)
    rho_particle = 1590.0 # kg/m^3
    d_particle_microns = 10.0
    d_particle = d_particle_microns * 1e-6 # m

    # Velocities
    v_high = 40.0 # m/s (60 psi estimate)
    v_low_min = 5.0 # m/s
    v_low_max = 10.0 # m/s

    print("--- Calculation Parameters ---")
    print(f"Tube Diameter (D): {d_tube_mm:.2f} mm")
    print(f"Coil Radius (Rc): {r_coil_mm:.2f} mm")
    print(f"Particle Diameter (dp): {d_particle_microns} microns")
    print(f"Fluid Density: {rho_air} kg/m^3")
    print(f"Fluid Viscosity: {mu_air} Pa·s")
    print("------------------------------\n")

    def calc_re(v):
        return (rho_air * v * d_tube) / mu_air

    def calc_de(re):
        return re * math.sqrt(d_tube / (2 * r_coil))

    def calc_stk(v):
        # Relaxation time tau_p
        tau_p = (rho_particle * (d_particle**2)) / (18 * mu_air)
        # Characteristic time tau_f = D / V
        # Or usually Characteristic Length Lc for curvature separation is D_tube/2 or Rc?
        # For impaction, usually D_obstacle. Here, maybe D_tube.
        # Let's use D_tube as the characteristic dimension for flow changes.
        tau_f = d_tube / v
        return tau_p / tau_f

    # --- High Pressure (60 psi) ---
    re_high = calc_re(v_high)
    de_high = calc_de(re_high)
    stk_high = calc_stk(v_high)

    print(f"--- 60 psi (Velocity ~{v_high} m/s) ---")
    print(f"Reynolds Number (Re): {re_high:.0f}")
    print(f"Dean Number (De): {de_high:.0f}")
    print(f"Stokes Number (Stk): {stk_high:.2f}")

    # --- Low Pressure (5-10 psi) ---
    re_low_min = calc_re(v_low_min)
    re_low_max = calc_re(v_low_max)

    de_low_min = calc_de(re_low_min)
    de_low_max = calc_de(re_low_max)

    stk_low_min = calc_stk(v_low_min)
    stk_low_max = calc_stk(v_low_max)

    print(f"\n--- 5-10 psi (Velocity {v_low_min}-{v_low_max} m/s) ---")
    print(f"Reynolds Number (Re): {re_low_min:.0f} - {re_low_max:.0f}")
    print(f"Dean Number (De): {de_low_min:.0f} - {de_low_max:.0f}")
    print(f"Stokes Number (Stk): {stk_low_min:.2f} - {stk_low_max:.2f}")

if __name__ == "__main__":
    calculate_physics()
