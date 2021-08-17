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
import { AreaModalFlowService } from '../modalflow/modalflow.service';
import { AreaService } from '../areas.service';
import { SpeciesSitesObsListComponent } from './list/list.component';
import { ProgramBaseComponent } from '../../base/program-base.component';
import { AuthService } from '../../../auth/auth.service';

@Component({
    selector: 'app-species-sites-obs',
    templateUrl: './observations.component.html',
    styleUrls: [
        '../../observations/obs.component.css',
        '../../../home/home.component.css',
        './observations.component.css',
    ],
    encapsulation: ViewEncapsulation.None,
})
export class SpeciesSitesObsComponent
    extends ProgramBaseComponent
    implements OnInit
{
    title = 'Observations';
    observations: FeatureCollection;
    userDashboard = false;
    @ViewChild(SpeciesSitesObsListComponent, { static: true })
    observationsList: SpeciesSitesObsListComponent;

    constructor(
        private router: Router,
        private route: ActivatedRoute,
        private programService: GncProgramsService,
        public flowService: AreaModalFlowService,
        public areaService: AreaService,
        authService: AuthService
    ) {
        super(authService);
        this.route.fragment.subscribe((fragment) => {
            this.fragment = fragment;
        });
    }

    ngOnInit() {
        this.route.params.subscribe((params) => {
            this.program_id = params['program_id'];

            this.verifyProgramPrivacyAndUser();

            this.loadData();
        });
    }

    loadData() {
        this.programService
            .getProgramSpeciesSitesObservations(this.program_id)
            .subscribe((observations) => {
                this.observations = observations;
            });
    }
}
