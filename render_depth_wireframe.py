import trimesh
import numpy as np
from PIL import Image, ImageDraw

def project_points(points, width, height, camera_pos, target, up, fov=60):
    # View Matrix
    z_axis = (camera_pos - target)
    z_axis = z_axis / np.linalg.norm(z_axis)
    x_axis = np.cross(up, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)

    view_matrix = np.eye(4)
    view_matrix[0, :3] = x_axis
    view_matrix[1, :3] = y_axis
    view_matrix[2, :3] = z_axis
    view_matrix[0, 3] = -np.dot(x_axis, camera_pos)
    view_matrix[1, 3] = -np.dot(y_axis, camera_pos)
    view_matrix[2, 3] = -np.dot(z_axis, camera_pos)

    # Transform to Camera Space
    points_h = np.hstack([points, np.ones((len(points), 1))])
    points_cam = (view_matrix @ points_h.T).T

    # Perspective Projection
    aspect = width / height
    f = 1.0 / np.tan(np.radians(fov) / 2)
    z_near = 0.1
    z_far = 1000.0

    projection_matrix = np.zeros((4, 4))
    projection_matrix[0, 0] = f / aspect
    projection_matrix[1, 1] = f
    projection_matrix[2, 2] = (z_far + z_near) / (z_near - z_far)
    projection_matrix[2, 3] = (2 * z_far * z_near) / (z_near - z_far)
    projection_matrix[3, 2] = -1

    points_clip = (projection_matrix @ points_cam.T).T

    # Perspective Divide
    w = points_clip[:, 3]
    w[w == 0] = 1e-6 # Avoid division by zero
    points_ndc = points_clip[:, :3] / w[:, np.newaxis]

    # Viewport Transform
    screen_points = np.zeros((len(points), 2))
    screen_points[:, 0] = (points_ndc[:, 0] + 1) * 0.5 * width
    screen_points[:, 1] = (1 - points_ndc[:, 1]) * 0.5 * height

    return screen_points, points_cam[:, 2]

def render_wireframe(stl_path, output_path):
    print(f"Loading {stl_path}...")
    mesh = trimesh.load(stl_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)

    edges = mesh.edges_unique
    vertices = mesh.vertices
    centroid = mesh.centroid

    # Camera setup
    camera_pos = centroid + np.array([50, -60, 40]) # Adjusted for better view
    target = centroid
    up = np.array([0, 0, 1])

    width, height = 1200, 900

    print("Projecting...")
    screen_pts, depths = project_points(vertices, width, height, camera_pos, target, up)

    # Calculate average Z per edge
    edge_z = []
    for i, edge in enumerate(edges):
        z1 = depths[edge[0]]
        z2 = depths[edge[1]]
        avg_z = (z1 + z2) / 2.0
        edge_z.append((avg_z, i))

    # Sort by Z (ascending, most negative first = furthest away)
    edge_z.sort(key=lambda x: x[0])

    # Determine depth range for cueing
    if not edge_z:
        print("No edges found!")
        return

    min_z = edge_z[0][0]
    max_z = edge_z[-1][0]
    z_range = max_z - min_z if max_z != min_z else 1.0

    print(f"Drawing {len(edges)} edges...")
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    for z, idx in edge_z:
        p1 = screen_pts[edges[idx][0]]
        p2 = screen_pts[edges[idx][1]]

        # Check if roughly on screen
        if (0 <= p1[0] <= width and 0 <= p1[1] <= height) or \
           (0 <= p2[0] <= width and 0 <= p2[1] <= height):

            # Depth Cueing
            # Normalized: 0 (furthest) to 1 (closest)
            norm = (z - min_z) / z_range

            # Thickness: 1 to 4
            line_width = 1 + 3 * norm

            # Color: Light Gray (furthest) to Black (closest)
            gray = int(180 * (1 - norm)) # 180 to 0
            color = (gray, gray, gray)

            draw.line([tuple(p1), tuple(p2)], fill=color, width=int(line_width))

    print(f"Saving to {output_path}...")
    img.save(output_path)
    print("Done.")

if __name__ == "__main__":
    render_wireframe("images/temp_helical.stl", "images/Wireframe view of Helical Geometry.png")
