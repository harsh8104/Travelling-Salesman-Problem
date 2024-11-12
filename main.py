import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import webbrowser
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from geopy.distance import geodesic
import math
import os

# Create the Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

class City:
    def __init__(self, name, lat, lon, is_map_selected=False):
        self.name = name
        self.lat = lat
        self.lon = lon
        self.is_map_selected = is_map_selected

    def distance(self, other):
        """Calculate distance in miles between self and another city."""
        return geodesic((self.lat, self.lon), (other.lat, other.lon)).miles

    def bearing(self, other):
        """Calculate compass bearing from self to another city."""
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        initial_bearing = math.atan2(y, x)
        compass_bearing = (math.degrees(initial_bearing) + 360) % 360
        return compass_bearing

class TSPSolver:
    def __init__(self, master):
        self.master = master
        self.master.title("TSP Solver with Animated Map")
        self.cities = []
        self.route = []
        self.map_selected_count = 0
        self.viewing_animation = False

        self.frame = ttk.Frame(master, padding="10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.add_city_button = ttk.Button(self.frame, text="Add City Manually", command=self.add_city_dialog)
        self.add_city_button.grid(row=0, column=0, padx=5, pady=5)

        self.solve_button = ttk.Button(self.frame, text="Solve TSP", command=self.solve_tsp)
        self.solve_button.grid(row=0, column=1, padx=5, pady=5)

        self.clear_button = ttk.Button(self.frame, text="Clear Cities", command=self.clear_cities)
        self.clear_button.grid(row=0, column=2, padx=5, pady=5)

        self.view_animation_button = ttk.Button(self.frame, text="View Animated Path", command=self.view_animated_path)
        self.view_animation_button.grid(row=0, column=3, padx=5, pady=5)

        self.add_cities_map_button = ttk.Button(self.frame, text="Add Cities on Map", command=self.add_cities_on_map)
        self.add_cities_map_button.grid(row=0, column=4, padx=5, pady=5)

        self.remove_city_button = ttk.Button(self.frame, text="Remove Selected City", command=self.remove_selected_city)
        self.remove_city_button.grid(row=0, column=5, padx=5, pady=5)

        self.cities_listbox = tk.Listbox(self.frame, width=50, height=10)
        self.cities_listbox.grid(row=1, column=0, columnspan=6, padx=5, pady=5)

        self.directions_tree = ttk.Treeview(self.frame, columns=('From', 'To', 'Distance', 'Direction'), show='headings')
        self.directions_tree.heading('From', text='From')
        self.directions_tree.heading('To', text='To')
        self.directions_tree.heading('Distance', text='Distance (miles)')
        self.directions_tree.heading('Direction', text='Direction')
        self.directions_tree.grid(row=2, column=0, columnspan=5, padx=5, pady=5, sticky=(tk.W, tk.E))

        self.scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.directions_tree.yview)
        self.scrollbar.grid(row=2, column=5, sticky=(tk.N, tk.S))
        self.directions_tree.configure(yscrollcommand=self.scrollbar.set)

        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=3, column=0, columnspan=6, sticky=(tk.W, tk.E))

    def update_status(self, message):
        self.status_var.set(message)

    def add_city_dialog(self):
        city_name = simpledialog.askstring("Input", "Enter City Name:")
        if not city_name:
            messagebox.showerror("Error", "City name cannot be empty.")
            return

        try:
            lat = float(simpledialog.askstring("Input", "Enter Latitude:"))
            lon = float(simpledialog.askstring("Input", "Enter Longitude:"))
        except ValueError:
            messagebox.showerror("Error", "Latitude and Longitude must be numbers.")
            return

        self.add_city(city_name, lat, lon)

    def add_city(self, name, lat, lon, is_map_selected=False):
        new_city = City(name, lat, lon, is_map_selected)
        self.cities.append(new_city)
        if is_map_selected:
            self.map_selected_count += 1
            display_name = str(self.map_selected_count)
        else:
            display_name = name
        self.cities_listbox.insert(tk.END, f"{display_name}: {lat:.4f}, {lon:.4f}")
        self.update_status(f"Added city: {display_name} at {lat:.4f}, {lon:.4f}")

    def clear_cities(self):
        self.cities.clear()
        self.route.clear()
        self.cities_listbox.delete(0, tk.END)
        self.directions_tree.delete(*self.directions_tree.get_children())
        self.map_selected_count = 0
        self.update_status("All cities cleared.")

    def remove_selected_city(self):
        selection = self.cities_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "No city selected.")
            return
        
        index = selection[0]
        removed_city = self.cities.pop(index)
        self.cities_listbox.delete(index)
        
        if removed_city.is_map_selected:
            self.map_selected_count -= 1
            self.renumber_map_selected_cities()
        
        self.update_status(f"Removed city: {removed_city.name} at {removed_city.lat:.4f}, {removed_city.lon:.4f}")

    def renumber_map_selected_cities(self):
        count = 0
        for i, city in enumerate(self.cities):
            if city.is_map_selected:
                count += 1
                city.name = str(count)
                self.cities_listbox.delete(i)
                self.cities_listbox.insert(i, f"{city.name}: {city.lat:.4f}, {city.lon:.4f}")

    def solve_tsp(self):
        if len(self.cities) < 2:
            self.update_status("Please add at least 2 cities before solving.")
            return

        self.update_status("Solving TSP...")
        self.route = self.nearest_neighbor()
        self.route = self.two_opt(self.route)
        self.display_directions()
        self.update_status("TSP solved. Directions displayed below. Use 'View Animated Path' to see the route on the map.")

    def nearest_neighbor(self):
        unvisited = self.cities[1:]
        route = [self.cities[0]]
        while unvisited:
            last = route[-1]
            next_city = min(unvisited, key=lambda city: last.distance(city))
            route.append(next_city)
            unvisited.remove(next_city)
        return route

    def two_opt(self, route):
        improvement = True
        while improvement:
            improvement = False
            for i in range(len(route) - 2):
                for j in range(i + 2, len(route)):
                    if j - i == 1:
                        continue
                    new_route = route[:]
                    new_route[i + 1:j + 1] = route[j:i:-1]
                    if self.route_length(new_route) < self.route_length(route):
                        route = new_route
                        improvement = True
        return route
    
    def route_length(self, route):
        return sum(city.distance(route[i + 1]) for i, city in enumerate(route[:-1])) + route[-1].distance(route[0])

    def display_directions(self):
        self.directions_tree.delete(*self.directions_tree.get_children())
        for i in range(len(self.route)):
            city1 = self.route[i]
            city2 = self.route[(i + 1) % len(self.route)]
            distance = city1.distance(city2)
            direction = city1.bearing(city2)
            self.directions_tree.insert('', 'end', values=(city1.name, city2.name, f"{distance:.2f}", f"{direction:.1f}°"))

        total_distance = self.route_length(self.route)
        self.directions_tree.insert('', 'end', values=('Total Distance', f"{total_distance:.2f} miles", '', ''))

    def view_animated_path(self):
        if len(self.cities) < 2:
            messagebox.showerror("Error", "Please add at least 2 cities before viewing the animated path.")
            return
        if not self.route:
            messagebox.showerror("Error", "Please solve the TSP first before viewing the animated path.")
            return
        self.viewing_animation = True
        webbrowser.open('http://localhost:5000/map')

    def add_cities_on_map(self):
        if self.viewing_animation:
            messagebox.showerror("Error", "Cannot add cities while viewing the animated path.")
            return
        webbrowser.open('http://localhost:5000/map')

    def generate_map_html(self):
        initial_location = [0, 0] if not self.cities else [self.cities[0].lat, self.cities[0].lon]
        cities_js = ', '.join([f'{{ "name": "{city.name}", "lat": {city.lat}, "lon": {city.lon} }}' for city in self.cities])
        route_js = self.get_route_coordinates()

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TSP Route Map with Animation</title>
            <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
            <style>
                html, body {{
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }}
                #map {{
                    width: 100%;
                    height: 100vh;
                }}
                .arrow {{
                    position: absolute;
                    width: 0;
                    height: 0;
                }}
                .arrow::before {{
                    content: '';
                    position: absolute;
                    top: -5px;
                    left: -5px;
                    width: 10px;
                    height: 10px;
                    background-color: red;
                    border-radius: 50%;
                }}
                .arrow::after {{
                    content: '';
                    position: absolute;
                    top: -3px;
                    left: 2px;
                    width: 0;
                    height: 0;
                    border-left: 6px solid red;
                    border-top: 3px solid transparent;
                    border-bottom: 3px solid transparent;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                var cities = [{cities_js}];
                var route = [{route_js}];
                var map = L.map('map').setView({initial_location}, 2);
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                }}).addTo(map);

                function addCity(lat, lon) {{
                    fetch('/add_city', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ lat: lat, lon: lon }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        var marker = L.marker([lat, lon]).addTo(map);
                        marker.bindPopup(data.name);
                    }});
                }}

                function drawRouteAnimated(route) {{
                    var i = 0;
                    function drawNextSegment() {{
                        if (i < route.length) {{
                            var start = route[i];
                            var end = route[(i + 1) % route.length];
                            var latlngs = [
                                [start.lat, start.lon],
                                [end.lat, end.lon]
                            ];
                            L.polyline(latlngs, {{"color": "blue", "weight": 2}}).addTo(map);

                            var cityNumber = i + 1;
                            var cityIcon = L.divIcon({{
                                className: 'city-number',
                                html: '<div style="background-color: white; border: 1px solid black; border-radius: 50%; width: 20px; height: 20px; text-align: center; line-height: 20px;">' + cityNumber + '</div>',
                                iconSize: [20, 20],
                                iconAnchor: [10, 10]
                            }});
                            L.marker([start.lat, start.lon], {{icon: cityIcon}}).addTo(map);

                            var midLat = (start.lat + end.lat) / 2;
                            var midLon = (start.lon + end.lon) / 2;

                            var angle = Math.atan2(end.lat - start.lat, end.lon - start.lon)
                            var arrowIcon = L.divIcon({{
                                className: 'arrow',
                                html: '<div style="transform: rotate(' + angle + 'deg);"></div>',
                                iconSize: [20, 20],
                                iconAnchor: [10, 10]
                            }});
                            L.marker([midLat, midLon], {{icon: arrowIcon}}).addTo(map);

                            i++;
                            setTimeout(drawNextSegment, 200); // 0.2 second delay
                        }}
                    }}
                    drawNextSegment();
                }}

                map.on('click', function(e) {{
                    if (!{str(self.viewing_animation).lower()}) {{
                        addCity(e.latlng.lat, e.latlng.lng);
                        }}
                }});

                if ({str(self.viewing_animation).lower()}) {{
                    drawRouteAnimated(route);
                }}
            </script>
        </body>
        </html>
        """
        
    def get_route_coordinates(self):
        return ', '.join([f'{{ "lat": {city.lat}, "lon": {city.lon} }}' for city in self.route])

@app.route('/add_city', methods=['POST'])
def add_city_api():
    if app_instance.viewing_animation:
        return jsonify({'error': 'Cannot add cities while viewing animation'}), 400
    
    data = request.get_json()
    lat = data.get('lat')
    lon = data.get('lon')
    app_instance.map_selected_count += 1
    city_name = str(app_instance.map_selected_count)
    new_city = City(city_name, lat, lon, is_map_selected=True)
    app_instance.cities.append(new_city)
    app_instance.cities_listbox.insert(tk.END, f"{city_name}: {lat:.4f}, {lon:.4f}")
    return jsonify({'name': city_name, 'message': f'Added {city_name}'})

@app.route('/map')
def map_view():
    map_html = app_instance.generate_map_html()
    return render_template_string(map_html)

@app.route('/')
def index():
    return render_template_string("""
    <h1>TSP Solver</h1>
    <p>Use the buttons in the main application to add cities, solve the TSP, or open the map.</p>
    """)

def run_flask():
    app.run(port=5000, debug=False)

if __name__ == "__main__":
    root = tk.Tk() 
    app_instance = TSPSolver(root)

    # Run Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run Tkinter main loop
    root.mainloop()