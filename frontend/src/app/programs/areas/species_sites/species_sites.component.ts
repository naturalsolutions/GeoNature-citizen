import {
    Component,
    OnInit,
    ViewEncapsulation,
    ViewChild,
    ViewChildren,
    QueryList,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { FeatureCollection } from 'geojson';

import { GncProgramsService } from '../../../api/gnc-programs.service';
import { Program } from '../../programs.models';
import { AreaModalFlowService } from '../modalflow/modalflow.service';
import { AreaService } from '../areas.service';
import { SpeciesSitesMapComponent } from './map/species_sites_map.component';
import { SpeciesSitesListComponent } from './list/list.component';
import { AreaModalFlowComponent } from '../modalflow/modalflow.component';
import { ProgramBaseComponent } from '../../base/program-base.component';

@Component({
    selector: 'app-species-sites',
    templateUrl: './species_sites.component.html',
    styleUrls: [
        '../../observations/obs.component.css',
        '../../../home/home.component.css',
        './species_sites.component.css',
    ],
    encapsulation: ViewEncapsulation.None,
})
export class SpeciesSitesComponent
    extends ProgramBaseComponent
    implements OnInit
{
    title = 'SpeciesSites';
    speciesSites: FeatureCollection;
    userDashboard = false;
    @ViewChild(SpeciesSitesMapComponent, { static: true })
    speciesSitesMap: SpeciesSitesMapComponent;
    @ViewChild(SpeciesSitesListComponent, { static: true })
    speciesSitesList: SpeciesSitesListComponent;
    @ViewChildren(AreaModalFlowComponent)
    modalFlow: QueryList<AreaModalFlowComponent>;
    area_id: number;

    constructor(
        private router: Router,
        private route: ActivatedRoute,
        private programService: GncProgramsService,
        public flowService: AreaModalFlowService,
        public areaService: AreaService
    ) {
        super();
        this.route.params.subscribe((params) => {
            this.program_id = params['program_id'];
        });
        this.route.fragment.subscribe((fragment) => {
            this.fragment = fragment;
        });
        this.areaService.newSpeciesSiteCreated.subscribe(
            (newSpeciesSiteFeature) => {
                this.loadSpeciesSites();
            }
        );
    }

    ngOnInit() {
        this.route.data.subscribe((data: { programs: Program[] }) => {
            // TODO: merge observables
            this.programs = data.programs;
            this.program = this.programs.find(
                (p) => p.id_program == this.program_id
            );
            this.loadSpeciesSites();
            this.programService
                .getProgram(this.program_id)
                .subscribe((program) => (this.programFeature = program));
        });
    }

    loadSpeciesSites() {
        this.programService
            .getProgramSpeciesSites(this.program_id)
            .subscribe((speciesSites) => {
                this.speciesSites = speciesSites;
            });
    }
}
