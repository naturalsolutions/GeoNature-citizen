import uuid

from flask import Blueprint, request, current_app, json
from geojson import FeatureCollection
from server import db

from shapely.geometry import asShape, Point
from geoalchemy2.shape import from_shape
from flask_jwt_extended import jwt_required

from .models import AreaModel, SpeciesSiteModel, SpeciesSiteObservationModel, SpeciesStageModel, StagesStepModel, \
    MediaOnSpeciesSiteObservationModel
from gncitizen.utils.errors import GeonatureApiError
from gncitizen.utils.jwt import get_id_role_if_exists
from gncitizen.utils.media import save_upload_files
from gncitizen.utils.sqlalchemy import get_geojson_feature, json_resp
from gncitizen.utils.taxonomy import get_specie_from_cd_nom, mkTaxonRepository
from gncitizen.core.users.models import UserModel
from gncitizen.core.commons.models import ProgramsModel, MediaModel

areas_api = Blueprint("areas", __name__)


def format_entity(data, with_geom=True):
    if with_geom:
        feature = get_geojson_feature(data.geom)
    else:
        feature = {"properties": {}}
    area_dict = data.as_dict(True)
    for k in area_dict:
        if k not in ("geom",):
            feature["properties"][k] = area_dict[k]
    return feature


def prepare_list(data, with_geom=True):
    count = len(data)
    features = []
    for element in data:
        formatted = format_entity(element, with_geom)
        features.append(formatted)
    data = FeatureCollection(features)
    data["count"] = count
    return data


"""Used attributes in observation features"""
obs_keys = (
    "id_species_site_observation",
    "observer",
    "id_program",
    "obs_txt",
    "count",
    "date",
    "timestamp_create",
    "json_data",
)


def generate_observation(id_species_site_observation):
    """generate observation from observation id

      :param id_species_site_observation: Observation unique id
      :type id_species_site_observation: int

      :return features: Observations as a Feature dict
      :rtype features: dict
    """

    # Crée le dictionnaire de l'observation
    observation = (
        db.session.query(
            SpeciesSiteObservationModel, UserModel.username
        )
            .join(SpeciesSiteModel, SpeciesSiteObservationModel.id_species_site == SpeciesSiteModel.id_species_site,
                  full=True)
            .join(UserModel, SpeciesSiteObservationModel.id_role == UserModel.id_user, full=True)
            .filter(SpeciesSiteObservationModel.id_species_site_observation == id_species_site_observation)
    ).one()

    photos = (
        db.session.query(MediaModel, SpeciesSiteObservationModel)
            .filter(SpeciesSiteObservationModel.id_species_site_observation == id_species_site_observation)
            .join(
            MediaOnSpeciesSiteObservationModel,
            MediaOnSpeciesSiteObservationModel.id_data_source == SpeciesSiteObservationModel.id_species_site_observation,
        )
            .join(MediaModel, MediaOnSpeciesSiteObservationModel.id_media == MediaModel.id_media)
            .all()
    )

    result_dict = observation.SpeciesSiteObservationModel.as_dict(True)
    result_dict["observer"] = {"username": observation.username}

    # Populate "geometry"
    features = []
    feature = get_geojson_feature(observation.SpeciesSiteObservationModel.species_site.geom)
    feature["properties"]["cd_nom"] = observation.SpeciesSiteObservationModel.species_site.cd_nom

    # Populate "properties"
    for k in result_dict:
        if k in obs_keys:
            feature["properties"][k] = result_dict[k]

    feature["properties"]["photos"] = [
        {
            "url": "/media/{}".format(p.MediaModel.filename),
            "date": p.SpeciesSiteObservationModel.as_dict()["date"],
            "author": p.SpeciesSiteObservationModel.obs_txt,
        }
        for p in photos
    ]

    taxhub_list_id = (
        ProgramsModel.query.filter_by(
            id_program=observation.SpeciesSiteObservationModel.species_site.area.id_program
        )
            .one()
            .taxonomy_list
    )
    taxon_repository = mkTaxonRepository(taxhub_list_id)
    try:
        taxon = next(
            taxon
            for taxon in taxon_repository
            if taxon and taxon["cd_nom"] == feature["properties"]["cd_nom"]
        )
        feature["properties"]["taxref"] = taxon["taxref"]
        feature["properties"]["medias"] = taxon["medias"]
    except StopIteration:
        pass

    features.append(feature)
    return features


@areas_api.route("/program/<int:pk>/jsonschema", methods=["GET"])
@json_resp
def get_area_jsonschema_by_program(pk):
    try:
        program = ProgramsModel.query.get(pk)
        data_dict = program.area_custom_form.json_schema
        return data_dict, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/<int:pk>/jsonschema", methods=["GET"])
@json_resp
def get_area_jsonschema(pk):
    try:
        area = AreaModel.query.get(pk)
        data_dict = area.program.area_custom_form.json_schema
        return data_dict, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/<int:pk>/species_site/jsonschema", methods=["GET"])
@json_resp
def get_species_site_jsonschema(pk):
    try:
        area = AreaModel.query.get(pk)
        data_dict = area.program.species_site_custom_form.json_schema
        return data_dict, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/species_site/<int:pk>/obs/jsonschema", methods=["GET"])
@json_resp
def get_species_site_obs_jsonschema(pk):
    try:
        species_site = SpeciesSiteModel.query.get(pk)
        data_dict = species_site.area.program.custom_form.json_schema
        return data_dict, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/program/<int:pk>/species_site/jsonschema", methods=["GET"])
@json_resp
def get_species_site_jsonschema_by_program(pk):
    try:
        program = ProgramsModel.query.get(pk)
        data_dict = program.species_site_custom_form.json_schema
        return data_dict, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/programs/<int:id>", methods=["GET"])
@json_resp
@jwt_required(optional=True)
def get_program_areas(id):
    """Get all areas
    ---
    tags:
      - Areas (External module)
    definitions:
      FeatureCollection:
        properties:
          type: dict
          description: area properties
        geometry:
          type: geojson
          description: GeoJson geometry
    responses:
      200:
        description: List of all areas
    """
    try:
        areas_query = AreaModel.query.filter_by(id_program=id)

        program = ProgramsModel.query.get(id)
        if program.is_private:
            user_id = get_id_role_if_exists()
            if user_id:
                areas_query = areas_query.filter_by(id_role=user_id)
            else:
                return prepare_list([])

        areas = areas_query.all()
        return prepare_list(areas)
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/program/<int:id>/species_sites/", methods=["GET"])
@json_resp
@jwt_required(optional=True)
def get_species_sites_by_program(id):
    """Get all program's species sites
    ---
    tags:
      - Areas (External module)
    definitions:
      FeatureCollection:
        properties:
          type: dict
          description: species site properties
        geometry:
          type: geojson
          description: GeoJson geometry
    responses:
      200:
        description: List of all species sites
    """
    try:
        species_sites_query = (SpeciesSiteModel.query
                               .join(AreaModel, AreaModel.id_area == SpeciesSiteModel.id_area)
                               .filter_by(id_program=id)
                               )

        program = ProgramsModel.query.get(id)
        if program.is_private:
            user_id = get_id_role_if_exists()
            if user_id:
                species_sites_query = species_sites_query.filter(SpeciesSiteModel.id_role == user_id)
            else:
                return prepare_list([])

        species_sites = species_sites_query.all()

        return prepare_list(species_sites)
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/program/<int:id>/observations/", methods=["GET"])
@json_resp
@jwt_required(optional=True)
def get_observations_by_program(id):
    """Get all program's observations
    ---
    tags:
      - Areas (External module)
    definitions:
      FeatureCollection:
        properties:
          type: dict
          description: species site properties
        geometry:
          type: geojson
          description: GeoJson geometry
    responses:
      200:
        description: List of all species sites
    """
    try:
        observations_query = (SpeciesSiteObservationModel.query
                              .join(SpeciesSiteModel,
                                    SpeciesSiteObservationModel.id_species_site == SpeciesSiteModel.id_species_site)
                              .join(AreaModel, AreaModel.id_area == SpeciesSiteModel.id_area)
                              .filter_by(id_program=id)
                              )

        program = ProgramsModel.query.get(id)
        if program.is_private:
            user_id = get_id_role_if_exists()
            if user_id:
                observations_query = observations_query.filter(SpeciesSiteObservationModel.id_role == user_id)
            else:
                return prepare_list([])

        observations = observations_query.all()

        return prepare_list(observations, with_geom=False)
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/<int:pk>", methods=["GET"])
@json_resp
def get_area(pk):
    """Get an area by id
    ---
    tags:
      - Areas (External module)
    parameters:
      - name: pk
        in: path
        type: integer
        required: true
        example: 1
    definitions:
      properties:
        type: dict
        description: area properties
      geometry:
        type: geojson
        description: GeoJson geometry
    responses:
      200:
        description: An area detail
    """
    try:
        area = AreaModel.query.get(pk)
        formatted_area = format_entity(area)
        species_sites = prepare_list(
            SpeciesSiteModel.query.filter_by(id_area=pk)
                .order_by(SpeciesSiteModel.timestamp_update.desc())
                .all()
        )
        formatted_area["properties"]["species_sites"] = species_sites
        return {"features": [formatted_area]}, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/species_sites/<int:pk>", methods=["GET"])
@json_resp
def get_species_site(pk):
    """Get an species site by id
    ---
    tags:
      - Areas (External module)
    parameters:
      - name: pk
        in: path
        type: integer
        required: true
        example: 1
    definitions:
      properties:
        type: dict
        description: species site properties
      geometry:
        type: geojson
        description: GeoJson geometry
    responses:
      200:
        description: A species site detail
    """
    try:
        species_site = SpeciesSiteModel.query.get(pk)
        formatted_species_site = format_entity(species_site)
        observations = prepare_list(
            SpeciesSiteObservationModel.query.filter_by(id_species_site=pk)
                .order_by(SpeciesSiteObservationModel.timestamp_update.desc())
                .all(),
            with_geom=False
        )
        stages = prepare_list(
            SpeciesStageModel.query.filter_by(cd_nom=species_site.cd_nom)
                .order_by(SpeciesStageModel.order.asc())
                .all(),
            with_geom=False
        )
        formatted_species_site["properties"]["observations"] = observations

        for stage in stages.features:
            steps = prepare_list(
                StagesStepModel.query.filter_by(id_species_stage=stage['properties']['id_species_stage'])
                    .order_by(StagesStepModel.order.asc())
                    .all(),
                with_geom=False
            )
            stage["properties"]["steps"] = steps

        formatted_species_site["properties"]["stages"] = stages

        return {"features": [formatted_species_site]}, 200
    except Exception as e:
        return {"error_message": str(e)}, 400


@areas_api.route("/", methods=["POST"])
@json_resp
@jwt_required(optional=True)
def post_area():
    """Ajout d'une zone
    Post an area
        ---
        tags:
          - Areas (External module)
        summary: Creates a new area
        consumes:
          - application/json
        produces:
          - application/json
        parameters:
          - name: body
            in: body
            description: JSON parameters.
            required: true
            schema:
              id: Area
              properties:
                id_program:
                  type: integer
                  description: Program foreign key
                  required: true
                  example: 1
                name:
                  type: string
                  description: Area name
                  default:  none
                  example: "Area 1"
                geometry:
                  type: string
                  example: {"type":"Point", "coordinates":[5,45]}
        responses:
          200:
            description: Area created
        """
    try:
        request_data = dict(request.get_json())

        datas2db = {}
        for field in request_data:
            if hasattr(AreaModel, field):
                datas2db[field] = request_data[field]
        current_app.logger.debug("datas2db: %s", datas2db)
        try:
            new_area = AreaModel(**datas2db)
        except Exception as e:
            current_app.logger.debug(e)
            raise GeonatureApiError(e)

        try:
            json_data = request_data.get("json_data")
            if json_data is not None:
                new_area.json_data = json.loads(json_data)
        except Exception as e:
            current_app.logger.warning("[post_observation] json_data ", e)
            raise GeonatureApiError(e)

        try:
            shape = asShape(request_data["geometry"])
            new_area.geom = from_shape(Point(shape), srid=4326)
        except Exception as e:
            current_app.logger.debug(e)
            raise GeonatureApiError(e)

        id_role = get_id_role_if_exists()
        if id_role is not None:
            new_area.id_role = id_role
            role = UserModel.query.get(id_role)
            new_area.obs_txt = role.username
            new_area.email = role.email
        else:
            if new_area.obs_txt is None or len(new_area.obs_txt) == 0:
                new_area.obs_txt = "Anonyme"

        new_area.uuid_sinp = uuid.uuid4()

        db.session.add(new_area)
        db.session.commit()
        # Réponse en retour
        result = AreaModel.query.get(new_area.id_area)
        return {"message": "New area created.", "features": [format_entity(result)]}, 200
    except Exception as e:
        current_app.logger.warning("Error: %s", str(e))
        return {"error_message": str(e)}, 400


@areas_api.route("/species_sites/", methods=["POST"])
@json_resp
@jwt_required(optional=True)
def post_species_site():
    """Ajout d'un site d'individu
    Post a species site
        ---
        tags:
          - Areas (External module)
        summary: Creates a new species site
        consumes:
          - application/json
        produces:
          - application/json
        parameters:
          - name: body
            in: body
            description: JSON parameters.
            required: true
            schema:
              id: Area
              properties:
                id_area:
                  type: integer
                  description: Area foreign key
                  required: true
                  example: 1
                name:
                  type: string
                  description: Species site name
                  default:  none
                  example: "Species site 1"
                geometry:
                  type: string
                  example: {"type":"Point", "coordinates":[5,45]}
        responses:
          200:
            description: Species site created
        """
    try:
        request_data = dict(request.get_json())

        datas2db = {}
        for field in request_data:
            if hasattr(SpeciesSiteModel, field):
                datas2db[field] = request_data[field]
        current_app.logger.debug("datas2db: %s", datas2db)
        try:
            new_species_site = SpeciesSiteModel(**datas2db)
        except Exception as e:
            current_app.logger.debug(e)
            raise GeonatureApiError(e)

        try:
            json_data = request_data.get("json_data")
            if json_data is not None:
                new_species_site.json_data = json.loads(json_data)
        except Exception as e:
            current_app.logger.warning("[post_observation] json_data ", e)
            raise GeonatureApiError(e)

        try:
            shape = asShape(request_data["geometry"])
            new_species_site.geom = from_shape(Point(shape), srid=4326)
        except Exception as e:
            current_app.logger.debug(e)
            raise GeonatureApiError(e)

        id_role = get_id_role_if_exists()
        if id_role is not None:
            new_species_site.id_role = id_role
            role = UserModel.query.get(id_role)
            new_species_site.obs_txt = role.username
            new_species_site.email = role.email
        else:
            if new_species_site.obs_txt is None or len(new_species_site.obs_txt) == 0:
                new_species_site.obs_txt = "Anonyme"

        new_species_site.uuid_sinp = uuid.uuid4()

        db.session.add(new_species_site)
        db.session.commit()
        # Réponse en retour
        result = SpeciesSiteModel.query.get(new_species_site.id_species_site)
        return {"message": "New species site created.", "features": [format_entity(result)]}, 200
    except Exception as e:
        current_app.logger.warning("Error: %s", str(e))
        return {"error_message": str(e)}, 400


@areas_api.route("/species_sites/<int:species_site_id>/observations", methods=["POST"])
@json_resp
@jwt_required(optional=True)
def post_observation(species_site_id):
    try:
        request_data = request.get_json()

        new_observation = SpeciesSiteObservationModel(
            id_species_site=species_site_id, date=request_data["date"], id_stages_step=request_data["stages_step_id"],
            json_data=request_data["data"]
        )

        id_role = get_id_role_if_exists()
        if id_role is not None:
            new_observation.id_role = id_role
            role = UserModel.query.get(id_role)
            new_observation.obs_txt = role.username
            new_observation.email = role.email
        else:
            if new_observation.obs_txt is None or len(new_visit.obs_txt) == 0:
                new_observation.obs_txt = "Anonyme"

        new_observation.uuid_sinp = uuid.uuid4()

        db.session.add(new_observation)
        db.session.commit()

        # Réponse en retour
        result = SpeciesSiteObservationModel.query.get(new_observation.id_species_site_observation)
        response_dict = result.as_dict()
        response_dict['program_id'] = result.species_site.area.id_program
        return {"message": "New observation created.", "features": [response_dict]}, 200
    except Exception as e:
        current_app.logger.warning("Error: %s", str(e))
        return {"error_message": str(e)}, 400


@areas_api.route("/species_sites/<int:site_id>/observations/<int:visit_id>/photos", methods=["POST"])
@json_resp
@jwt_required(optional=True)
def post_observation_photo(species_site_id, observation_id):
    try:
        current_app.logger.debug("UPLOAD FILE? " + str(request.files))
        if request.files:
            files = save_upload_files(
                request.files, "species_site_id", species_site_id, observation_id, MediaOnSpeciesSiteObservationModel,
            )
            current_app.logger.debug("UPLOAD FILE {}".format(files))
            return files, 200
        return [], 200
    except Exception as e:
        current_app.logger.error("Error: %s", str(e))
        return {"error_message": str(e)}, 400


@areas_api.route("/observations/<int:pk>", methods=["GET"])
@json_resp
def get_observation(pk):
    """Get on observation by id
         ---
         tags:
          - observations
         parameters:
          - name: pk
            in: path
            type: integer
            required: true
            example: 1
         definitions:
           name:
             type: string
         responses:
           200:
             description: A list of all observations
         """
    try:
        features = generate_observation(pk)
        return {"features": features}, 200
    except Exception as e:
        return {"message": str(e)}, 400
